import struct
import sys
import os
from pathlib import Path
from typing import Tuple, Optional

# Constants
QOI_MAGIC = b'qoif'
QOI_HEADER_SIZE = 14
QOI_PIXELS_MAX = 400000000
QOI_SRGB = 0
QOI_LINEAR = 1
QOI_PADDING = b'\x00\x00\x00\x00\x00\x00\x00\x01'

# Op Codes
QOI_OP_INDEX = 0x00
QOI_OP_DIFF  = 0x40
QOI_OP_LUMA  = 0x80
QOI_OP_RUN   = 0xc0
QOI_OP_RGB   = 0xfe
QOI_OP_RGBA  = 0xff
QOI_MASK_2   = 0xc0

class QOIEncoder:
    def encode(self, pixels: bytes, width: int, height: int, channels: int, colorspace: int) -> Tuple[bytes, int]:
        # Size validation
        if (width == 0 or height == 0 or 
            channels < 3 or channels > 4 or 
            colorspace > 1 or 
            height >= QOI_PIXELS_MAX // width):
            return b'', 0
        
        px_len = width * height
        max_size = QOI_HEADER_SIZE + px_len * 5 + 8
        
        # Pre-allocate output buffer
        output = bytearray(max_size)
        
        # Write header
        struct.pack_into('>4sIIBB', output, 0, QOI_MAGIC, width, height, channels, colorspace)
        out_pos = QOI_HEADER_SIZE
        
        # ---------------------------------------------------------
        # THE OPTIMIZATION ZONE
        # ---------------------------------------------------------
        
        # We use a standard List for the index. It is faster than array.array
        # for frequent updates in CPython.
        index = [0] * 64 
        
        # Flatten the input to a memoryview to avoid string copying
        pixel_data = memoryview(pixels)
        
        # Previous pixel state
        prev_r, prev_g, prev_b, prev_a = 0, 0, 0, 255
        prev_px_int = (255 << 24) # 0x000000FF in standard QOI packing logic
        
        run = 0
        
        # Local variable caching (The holy grail of python speed)
        # We bind these to locals so the interpreter doesn't search the global scope
        qoi_op_run = QOI_OP_RUN
        qoi_op_index = QOI_OP_INDEX
        qoi_op_diff = QOI_OP_DIFF
        qoi_op_luma = QOI_OP_LUMA
        qoi_op_rgb = QOI_OP_RGB
        qoi_op_rgba = QOI_OP_RGBA
        
        # Calculate end point for the loop
        total_bytes = len(pixels)
        last_pixel_index = total_bytes - channels
        
        # ---------------------------------------------------------
        # THE LOOP
        # We manually index the bytes. No slicing [i:i+4].
        # Slicing creates a new object. We don't want new objects.
        # ---------------------------------------------------------
        
        if channels == 4:
            for i in range(0, total_bytes, 4):
                # Direct access. SPEED.
                r = pixel_data[i]
                g = pixel_data[i+1]
                b = pixel_data[i+2]
                a = pixel_data[i+3]

                # Combined integer for hashing and equality check
                # (R, G, B, A) -> Int
                px_int = (r << 24) | (g << 16) | (b << 8) | a

                if px_int == prev_px_int:
                    run += 1
                    if run == 62 or i == last_pixel_index:
                        output[out_pos] = qoi_op_run | (run - 1)
                        out_pos += 1
                        run = 0
                    continue
                
                if run > 0:
                    output[out_pos] = qoi_op_run | (run - 1)
                    out_pos += 1
                    run = 0

                # Hash: (r * 3 + g * 5 + b * 7 + a * 11) % 64
                idx_pos = (r * 3 + g * 5 + b * 7 + a * 11) & 63
                
                if index[idx_pos] == px_int:
                    output[out_pos] = qoi_op_index | idx_pos
                    out_pos += 1
                    # Update previous pixel state cache
                    prev_px_int = px_int
                    prev_r, prev_g, prev_b, prev_a = r, g, b, a
                    continue

                index[idx_pos] = px_int

                if a == prev_a:
                    vr = r - prev_r
                    vg = g - prev_g
                    vb = b - prev_b
                    
                    # DIFF OP (2-bit differences)
                    # Checking bounds: -2..1
                    if -2 <= vr <= 1 and -2 <= vg <= 1 and -2 <= vb <= 1:
                        output[out_pos] = qoi_op_diff | ((vr + 2) << 4) | ((vg + 2) << 2) | (vb + 2)
                        out_pos += 1
                    
                    # LUMA OP (Green diff + dr_dg + db_dg)
                    else:
                        vg_r = vr - vg
                        vg_b = vb - vg
                        # Checking bounds: vg: -32..31, others: -8..7
                        if -32 <= vg <= 31 and -8 <= vg_r <= 7 and -8 <= vg_b <= 7:
                            output[out_pos] = qoi_op_luma | (vg + 32)
                            output[out_pos + 1] = ((vg_r + 8) << 4) | (vg_b + 8)
                            out_pos += 2
                        else:
                            # RGB (Alpha matches)
                            output[out_pos] = qoi_op_rgb
                            output[out_pos+1] = r
                            output[out_pos+2] = g
                            output[out_pos+3] = b
                            out_pos += 4
                else:
                    # RGBA (Full pixel)
                    output[out_pos] = qoi_op_rgba
                    output[out_pos+1] = r
                    output[out_pos+2] = g
                    output[out_pos+3] = b
                    output[out_pos+4] = a
                    out_pos += 5

                prev_px_int = px_int
                prev_r, prev_g, prev_b, prev_a = r, g, b, a
        
        # ---------------------------------------------------------
        # Same logic but for 3 channels (RGB)
        # ---------------------------------------------------------
        else:
            for i in range(0, total_bytes, 3):
                r = pixel_data[i]
                g = pixel_data[i+1]
                b = pixel_data[i+2]
                a = 255 # Hardcoded opaque for RGB images

                px_int = (r << 24) | (g << 16) | (b << 8) | a

                if px_int == prev_px_int:
                    run += 1
                    if run == 62 or i == last_pixel_index:
                        output[out_pos] = qoi_op_run | (run - 1)
                        out_pos += 1
                        run = 0
                    continue
                
                if run > 0:
                    output[out_pos] = qoi_op_run | (run - 1)
                    out_pos += 1
                    run = 0

                idx_pos = (r * 3 + g * 5 + b * 7 + a * 11) & 63
                
                if index[idx_pos] == px_int:
                    output[out_pos] = qoi_op_index | idx_pos
                    out_pos += 1
                    prev_px_int = px_int
                    prev_r, prev_g, prev_b, prev_a = r, g, b, a
                    continue

                index[idx_pos] = px_int

                # Since source is RGB, Alpha (255) always matches previous Alpha (255)
                # We only need to check DIFF, LUMA, or RGB
                vr = r - prev_r
                vg = g - prev_g
                vb = b - prev_b

                if -2 <= vr <= 1 and -2 <= vg <= 1 and -2 <= vb <= 1:
                    output[out_pos] = qoi_op_diff | ((vr + 2) << 4) | ((vg + 2) << 2) | (vb + 2)
                    out_pos += 1
                else:
                    vg_r = vr - vg
                    vg_b = vb - vg
                    if -32 <= vg <= 31 and -8 <= vg_r <= 7 and -8 <= vg_b <= 7:
                        output[out_pos] = qoi_op_luma | (vg + 32)
                        output[out_pos + 1] = ((vg_r + 8) << 4) | (vg_b + 8)
                        out_pos += 2
                    else:
                        output[out_pos] = qoi_op_rgb
                        output[out_pos+1] = r
                        output[out_pos+2] = g
                        output[out_pos+3] = b
                        out_pos += 4

                prev_px_int = px_int
                prev_r, prev_g, prev_b, prev_a = r, g, b, a

        output[out_pos:out_pos+8] = QOI_PADDING
        out_pos += 8
        
        return bytes(output[:out_pos]), out_pos


class QOIDecoder:
    def decode(self, data: bytes, channels: int = 0) -> Tuple[Optional[bytes], int, int, int, int]:
        if len(data) < QOI_HEADER_SIZE + 8:
            return None, 0, 0, 0, 0
        
        # Unpack header
        magic, width, height, desc_channels, colorspace = struct.unpack_from('>4sIIBB', data, 0)
        
        if magic != QOI_MAGIC or width == 0 or height == 0:
            return None, 0, 0, 0, 0

        out_channels = channels if channels != 0 else desc_channels
        px_count = width * height
        output_size = px_count * out_channels
        
        output = bytearray(output_size)
        index = [0] * 64
        
        # Colors
        r, g, b, a = 0, 0, 0, 255
        
        data_len = len(data) - 8
        p = QOI_HEADER_SIZE
        run = 0
        out_pos = 0
        
        # Local caching
        qoi_op_index = QOI_OP_INDEX
        qoi_op_diff = QOI_OP_DIFF
        qoi_op_luma = QOI_OP_LUMA
        qoi_op_run = QOI_OP_RUN
        qoi_op_rgb = QOI_OP_RGB
        qoi_op_rgba = QOI_OP_RGBA
        qoi_mask_2 = QOI_MASK_2
        
        # ---------------------------------------------------------
        # DECODER LOOP OPTIMIZATION
        # ---------------------------------------------------------
        
        # Split loops based on output channels to avoid "if out_channels == 4" check inside the loop
        if out_channels == 4:
            for _ in range(px_count):
                if run > 0:
                    run -= 1
                elif p < data_len:
                    b1 = data[p]
                    p += 1
                    
                    if b1 == qoi_op_rgb:
                        r, g, b = data[p], data[p+1], data[p+2]
                        p += 3
                    elif b1 == qoi_op_rgba:
                        r, g, b, a = data[p], data[p+1], data[p+2], data[p+3]
                        p += 4
                    elif (b1 & qoi_mask_2) == qoi_op_index:
                        px = index[b1 & 63]
                        r = (px >> 24) & 0xFF
                        g = (px >> 16) & 0xFF
                        b = (px >> 8) & 0xFF
                        a = px & 0xFF
                    elif (b1 & qoi_mask_2) == qoi_op_diff:
                        r = (r + ((b1 >> 4) & 0x03) - 2) & 0xFF
                        g = (g + ((b1 >> 2) & 0x03) - 2) & 0xFF
                        b = (b + (b1 & 0x03) - 2) & 0xFF
                    elif (b1 & qoi_mask_2) == qoi_op_luma:
                        b2 = data[p]
                        p += 1
                        vg = (b1 & 0x3F) - 32
                        r = (r + vg - 8 + ((b2 >> 4) & 0x0F)) & 0xFF
                        g = (g + vg) & 0xFF
                        b = (b + vg - 8 + (b2 & 0x0F)) & 0xFF
                    elif (b1 & qoi_mask_2) == qoi_op_run:
                        run = (b1 & 0x3F)
                    
                    idx_pos = (r * 3 + g * 5 + b * 7 + a * 11) & 63
                    index[idx_pos] = (r << 24) | (g << 16) | (b << 8) | a

                output[out_pos] = r
                output[out_pos+1] = g
                output[out_pos+2] = b
                output[out_pos+3] = a
                out_pos += 4
                
        else: # out_channels == 3
            for _ in range(px_count):
                if run > 0:
                    run -= 1
                elif p < data_len:
                    b1 = data[p]
                    p += 1
                    
                    if b1 == qoi_op_rgb:
                        r, g, b = data[p], data[p+1], data[p+2]
                        p += 3
                    elif b1 == qoi_op_rgba:
                        r, g, b, a = data[p], data[p+1], data[p+2], data[p+3]
                        p += 4
                    elif (b1 & qoi_mask_2) == qoi_op_index:
                        px = index[b1 & 63]
                        r = (px >> 24) & 0xFF
                        g = (px >> 16) & 0xFF
                        b = (px >> 8) & 0xFF
                        a = px & 0xFF
                    elif (b1 & qoi_mask_2) == qoi_op_diff:
                        r = (r + ((b1 >> 4) & 0x03) - 2) & 0xFF
                        g = (g + ((b1 >> 2) & 0x03) - 2) & 0xFF
                        b = (b + (b1 & 0x03) - 2) & 0xFF
                    elif (b1 & qoi_mask_2) == qoi_op_luma:
                        b2 = data[p]
                        p += 1
                        vg = (b1 & 0x3F) - 32
                        r = (r + vg - 8 + ((b2 >> 4) & 0x0F)) & 0xFF
                        g = (g + vg) & 0xFF
                        b = (b + vg - 8 + (b2 & 0x0F)) & 0xFF
                    elif (b1 & qoi_mask_2) == qoi_op_run:
                        run = (b1 & 0x3F)
                    
                    idx_pos = (r * 3 + g * 5 + b * 7 + a * 11) & 63
                    index[idx_pos] = (r << 24) | (g << 16) | (b << 8) | a

                output[out_pos] = r
                output[out_pos+1] = g
                output[out_pos+2] = b
                out_pos += 3
                
        return bytes(output), width, height, desc_channels, colorspace

class QOICodec:
    # Use existing codec wrapper logic
    def __init__(self):
        self.encoder = QOIEncoder()
        self.decoder = QOIDecoder()
        
    def encode_file(self, input_path: str, output_path: str, colorspace: int = QOI_SRGB) -> int:
        try:
            from PIL import Image
            img = Image.open(input_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            pixels = img.tobytes()
            width, height = img.size
            
            # Since we forced RGBA in PIL, channels is 4
            encoded, size = self.encoder.encode(pixels, width, height, 4, colorspace)
            
            if size == 0: return 0
            with open(output_path, 'wb') as f:
                f.write(encoded)
            return size
        except ImportError:
            print("Girl you need PIL. pip install Pillow.")
            return 0
    
    def decode_file(self, input_path: str, output_path: str, force_channels: int = 0) -> bool:
        try:
            with open(input_path, 'rb') as f:
                data = f.read()
            pixels, width, height, channels, _ = self.decoder.decode(data, force_channels)
            if pixels is None: return False
            from PIL import Image
            mode = 'RGBA' if channels == 4 else 'RGB'
            img = Image.frombytes(mode, (width, height), pixels)
            img.save(output_path, 'PNG')
            return True
        except Exception:
            return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python qoi.py <file>")
        sys.exit(1)
        
    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print("File wrong. Bye.")
        sys.exit(1)
        
    codec = QOICodec()
    p = Path(input_file)
    
    if p.suffix.lower() in ['.png', '.jpg', '.jpeg']:
        print(f"💅 Compressing {input_file}...")
        s = codec.encode_file(input_file, str(p.with_suffix('.qoi')))
        print(f"🔥 Size: {s:,} bytes") if s else print("💀 Fail.")
    elif p.suffix.lower() == '.qoi':
        print(f"💅 Expanding {input_file}...")
        ok = codec.decode_file(input_file, str(p.with_suffix('.png')))
        print("✨ Fabulous.") if ok else print("💀 Fail.")
    else:
        print("Unknown file type. I don't know her.")

if __name__ == "__main__":
    main()
