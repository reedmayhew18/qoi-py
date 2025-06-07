import struct
import sys
import os
from pathlib import Path
from typing import Tuple, Optional
import array

# QOI Constants
QOI_OP_INDEX = 0x00  # 00xxxxxx
QOI_OP_DIFF = 0x40   # 01xxxxxx
QOI_OP_LUMA = 0x80   # 10xxxxxx
QOI_OP_RUN = 0xc0    # 11xxxxxx
QOI_OP_RGB = 0xfe    # 11111110
QOI_OP_RGBA = 0xff   # 11111111

QOI_MASK_2 = 0xc0    # 11000000

QOI_MAGIC = b'qoif'
QOI_HEADER_SIZE = 14
QOI_SRGB = 0
QOI_LINEAR = 1

QOI_PIXELS_MAX = 400000000

# Pre-create padding constant
QOI_PADDING = b'\x00\x00\x00\x00\x00\x00\x00\x01'

class QOIEncoder:
    def __init__(self):
        # Pre-allocate flat color index (64 entries * 4 bytes = 256 bytes)
        self._index = array.array('I', [0xFF000000] * 64)  # Initialize with opaque black
        
    def encode(self, pixels: bytes, width: int, height: int, channels: int, colorspace: int) -> Tuple[bytes, int]:
        """Encode raw pixel data to QOI format. Returns (data, size)."""
        if (width == 0 or height == 0 or 
            channels < 3 or channels > 4 or 
            colorspace > 1 or 
            height >= QOI_PIXELS_MAX // width):
            return b'', 0
        
        px_len = width * height
        max_size = QOI_HEADER_SIZE + px_len * 5 + 8  # Worst case: all RGBA ops
        
        # Pre-allocate output buffer
        output = bytearray(max_size)
        out_pos = 0
        
        # Write header directly
        output[out_pos:out_pos+4] = QOI_MAGIC
        out_pos += 4
        struct.pack_into('>II', output, out_pos, width, height)
        out_pos += 8
        output[out_pos] = channels
        output[out_pos + 1] = colorspace
        out_pos += 2
        
        # Reset index - all entries to opaque black
        index = self._index
        for i in range(64):
            index[i] = 0xFF000000
        
        # Previous pixel as packed 32-bit integer (0xAARRGGBB)
        px_prev = 0xFF000000
        run = 0
        
        # Cache frequently used values
        px_pos = 0
        px_end = px_len * channels
        
        # Main encoding loop
        while px_pos < px_end:
            # Pack current pixel into 32-bit integer
            r = pixels[px_pos]
            g = pixels[px_pos + 1]
            b = pixels[px_pos + 2]
            a = pixels[px_pos + 3] if channels == 4 else 255
            px = (a << 24) | (r << 16) | (g << 8) | b
            
            # Single comparison for run detection
            if px == px_prev:
                run += 1
                if run == 62 or px_pos + channels >= px_end:
                    output[out_pos] = QOI_OP_RUN | (run - 1)
                    out_pos += 1
                    run = 0
            else:
                # Flush any pending run
                if run > 0:
                    output[out_pos] = QOI_OP_RUN | (run - 1)
                    out_pos += 1
                    run = 0
                
                # Calculate hash using bitwise AND
                hash_val = (r * 3 + g * 5 + b * 7 + a * 11) & 63
                
                # Check if pixel is in index
                if index[hash_val] == px:
                    output[out_pos] = QOI_OP_INDEX | hash_val
                    out_pos += 1
                else:
                    # Update index
                    index[hash_val] = px
                    
                    # Extract previous pixel components
                    px_prev_a = px_prev >> 24
                    px_prev_r = (px_prev >> 16) & 0xFF
                    px_prev_g = (px_prev >> 8) & 0xFF
                    px_prev_b = px_prev & 0xFF
                    
                    if a == px_prev_a:  # Same alpha
                        # Calculate signed differences
                        vr = r - px_prev_r
                        vg = g - px_prev_g
                        vb = b - px_prev_b
                        
                        vg_r = vr - vg
                        vg_b = vb - vg
                        
                        # Check DIFF bounds
                        if -2 <= vr <= 1 and -2 <= vg <= 1 and -2 <= vb <= 1:
                            output[out_pos] = QOI_OP_DIFF | ((vr + 2) << 4) | ((vg + 2) << 2) | (vb + 2)
                            out_pos += 1
                        # Check LUMA bounds
                        elif -32 <= vg <= 31 and -8 <= vg_r <= 7 and -8 <= vg_b <= 7:
                            output[out_pos] = QOI_OP_LUMA | (vg + 32)
                            output[out_pos + 1] = ((vg_r + 8) << 4) | (vg_b + 8)
                            out_pos += 2
                        else:
                            # RGB operation
                            output[out_pos] = QOI_OP_RGB
                            output[out_pos + 1] = r
                            output[out_pos + 2] = g
                            output[out_pos + 3] = b
                            out_pos += 4
                    else:
                        # RGBA operation
                        output[out_pos] = QOI_OP_RGBA
                        output[out_pos + 1] = r
                        output[out_pos + 2] = g
                        output[out_pos + 3] = b
                        output[out_pos + 4] = a
                        out_pos += 5
                
                px_prev = px
            
            px_pos += channels
        
        # Add padding using slicing
        output[out_pos:out_pos+8] = QOI_PADDING
        out_pos += 8
        
        return bytes(output[:out_pos]), out_pos


class QOIDecoder:
    def __init__(self):
        # Pre-allocate flat color index
        self._index = array.array('I', [0xFF000000] * 64)
        
    def decode(self, data: bytes, channels: int = 0) -> Tuple[Optional[bytes], int, int, int, int]:
        """Decode QOI data to raw pixels. Returns (pixels, width, height, channels, colorspace)."""
        if len(data) < QOI_HEADER_SIZE + 8:
            return None, 0, 0, 0, 0
        
        # Read header
        if data[0:4] != QOI_MAGIC:
            return None, 0, 0, 0, 0
        
        width, height = struct.unpack_from('>II', data, 4)
        desc_channels = data[12]
        colorspace = data[13]
        
        if (width == 0 or height == 0 or 
            desc_channels < 3 or desc_channels > 4 or 
            colorspace > 1 or
            height >= QOI_PIXELS_MAX // width):
            return None, 0, 0, 0, 0
        
        if channels == 0:
            channels = desc_channels
        
        px_len = width * height * channels
        
        # Pre-allocate output buffer
        output = bytearray(px_len)
        out_pos = 0
        
        # Reset index
        index = self._index
        for i in range(64):
            index[i] = 0xFF000000
        
        # Current pixel as packed integer
        px = 0xFF000000
        run = 0
        
        chunks_len = len(data) - 8
        p = QOI_HEADER_SIZE
        
        # Main decode loop
        px_count = width * height
        for _ in range(px_count):
            if run > 0:
                run -= 1
            elif p < chunks_len:
                b1 = data[p]
                p += 1
                
                if b1 == QOI_OP_RGB:
                    r = data[p]
                    g = data[p + 1]
                    b = data[p + 2]
                    a = (px >> 24) & 0xFF  # Keep previous alpha
                    px = (a << 24) | (r << 16) | (g << 8) | b
                    p += 3
                elif b1 == QOI_OP_RGBA:
                    r = data[p]
                    g = data[p + 1]
                    b = data[p + 2]
                    a = data[p + 3]
                    px = (a << 24) | (r << 16) | (g << 8) | b
                    p += 4
                elif (b1 & QOI_MASK_2) == QOI_OP_INDEX:
                    px = index[b1 & 63]
                elif (b1 & QOI_MASK_2) == QOI_OP_DIFF:
                    # Extract current components
                    a = (px >> 24) & 0xFF
                    r = (px >> 16) & 0xFF
                    g = (px >> 8) & 0xFF
                    b = px & 0xFF
                    # Apply diffs
                    r = (r + ((b1 >> 4) & 0x03) - 2) & 0xFF
                    g = (g + ((b1 >> 2) & 0x03) - 2) & 0xFF
                    b = (b + (b1 & 0x03) - 2) & 0xFF
                    px = (a << 24) | (r << 16) | (g << 8) | b
                elif (b1 & QOI_MASK_2) == QOI_OP_LUMA:
                    b2 = data[p]
                    p += 1
                    # Extract current components
                    a = (px >> 24) & 0xFF
                    r = (px >> 16) & 0xFF
                    g = (px >> 8) & 0xFF
                    b = px & 0xFF
                    # Apply luma
                    vg = (b1 & 0x3F) - 32
                    r = (r + vg - 8 + ((b2 >> 4) & 0x0F)) & 0xFF
                    g = (g + vg) & 0xFF
                    b = (b + vg - 8 + (b2 & 0x0F)) & 0xFF
                    px = (a << 24) | (r << 16) | (g << 8) | b
                elif (b1 & QOI_MASK_2) == QOI_OP_RUN:
                    run = (b1 & 0x3F)
                
                # Update index
                r = (px >> 16) & 0xFF
                g = (px >> 8) & 0xFF
                b = px & 0xFF
                a = (px >> 24) & 0xFF
                hash_val = (r * 3 + g * 5 + b * 7 + a * 11) & 63
                index[hash_val] = px
            
            # Unpack pixel to output
            if channels == 4:
                output[out_pos] = (px >> 16) & 0xFF  # R
                output[out_pos + 1] = (px >> 8) & 0xFF   # G
                output[out_pos + 2] = px & 0xFF          # B
                output[out_pos + 3] = (px >> 24) & 0xFF  # A
                out_pos += 4
            else:
                output[out_pos] = (px >> 16) & 0xFF  # R
                output[out_pos + 1] = (px >> 8) & 0xFF   # G
                output[out_pos + 2] = px & 0xFF          # B
                out_pos += 3
        
        return bytes(output), width, height, desc_channels, colorspace


# Wrapper class for file operations
class QOICodec:
    def __init__(self):
        self.encoder = QOIEncoder()
        self.decoder = QOIDecoder()
        
    def encode_file(self, input_path: str, output_path: str, colorspace: int = QOI_SRGB) -> int:
        """Encode a PNG or JPG image to QOI format."""
        try:
            # Only use PIL for file I/O
            from PIL import Image
            
            img = Image.open(input_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Get raw bytes
            pixels = img.tobytes()
            width, height = img.size
            channels = 4
            
            # Encode
            encoded, size = self.encoder.encode(pixels, width, height, channels, colorspace)
            
            if size == 0:
                return 0
            
            # Write to file
            with open(output_path, 'wb') as f:
                f.write(encoded)
            
            return size
            
        except ImportError:
            print("PIL is required for image file I/O")
            return 0
    
    def decode_file(self, input_path: str, output_path: str, force_channels: int = 0) -> bool:
        """Decode a QOI image to PNG format."""
        try:
            # Read QOI file
            with open(input_path, 'rb') as f:
                data = f.read()
            
            # Decode
            pixels, width, height, channels, colorspace = self.decoder.decode(data, force_channels)
            
            if pixels is None:
                return False
            
            # Only use PIL for file I/O
            from PIL import Image
            
            # Create image from raw bytes
            if force_channels > 0:
                channels = force_channels
                
            mode = 'RGBA' if channels == 4 else 'RGB'
            img = Image.frombytes(mode, (width, height), pixels)
            
            # Save
            img.save(output_path, 'PNG')
            return True
            
        except ImportError:
            print("PIL is required for image file I/O")
            return False
        except Exception as e:
            print(f"Error: {e}")
            return False


def main():
    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python qoi_converter.py <input_file>")
        print("  Converts PNG/JPG to QOI, or QOI to PNG")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found")
        sys.exit(1)
    
    # Get file extension
    input_path = Path(input_file)
    extension = input_path.suffix.lower()
    
    codec = QOICodec()
    
    if extension in ['.png', '.jpg', '.jpeg']:
        # Convert to QOI
        output_file = input_path.with_suffix('.qoi')
        print(f"Converting {input_file} to QOI format...")
        
        try:
            bytes_written = codec.encode_file(input_file, str(output_file))
            if bytes_written > 0:
                print(f"✓ Successfully created {output_file} ({bytes_written:,} bytes)")
                
                # Calculate compression ratio if possible
                input_size = os.path.getsize(input_file)
                ratio = (input_size / bytes_written) if bytes_written > 0 else 0
                print(f"  Compression ratio: {ratio:.2f}:1")
            else:
                print(f"✗ Failed to encode {input_file}")
                sys.exit(1)
        except Exception as e:
            print(f"✗ Error encoding file: {e}")
            sys.exit(1)
            
    elif extension == '.qoi':
        # Convert to PNG
        output_file = input_path.with_suffix('.png')
        print(f"Converting {input_file} to PNG format...")
        
        try:
            success = codec.decode_file(input_file, str(output_file))
            if success:
                output_size = os.path.getsize(output_file)
                print(f"✓ Successfully created {output_file} ({output_size:,} bytes)")
            else:
                print(f"✗ Failed to decode {input_file}")
                sys.exit(1)
        except Exception as e:
            print(f"✗ Error decoding file: {e}")
            sys.exit(1)
            
    else:
        print(f"Error: Unsupported file format '{extension}'")
        print("Supported formats: PNG, JPG/JPEG (for encoding), QOI (for decoding)")
        sys.exit(1)


if __name__ == "__main__":
    main()
