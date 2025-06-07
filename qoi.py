import struct
import sys
import os
from PIL import Image
#Use Numpy
import numpy as np
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

def qoi_color_hash(r: int, g: int, b: int, a: int) -> int:
    """Calculate hash for color index."""
    return (r * 3 + g * 5 + b * 7 + a * 11) & 63  # Use bitwise AND instead of modulo

class QOICodec:
    def __init__(self):
        self.padding = QOI_PADDING
        # Pre-allocate reusable buffers
        self._index_buffer = [0] * 256  # 64 * 4 components
        self._output_buffer = bytearray(1024 * 1024)  # 1MB initial buffer
    
    def encode_file(self, input_path: str, output_path: str, colorspace: int = QOI_SRGB) -> int:
        """Encode a PNG or JPG image to QOI format."""
        # Load image using PIL
        img = Image.open(input_path)
        
        # Convert to RGBA if necessary
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Get image data as numpy array - ensure C-contiguous for faster access
        pixels = np.ascontiguousarray(img, dtype=np.uint8)
        height, width = pixels.shape[:2]
        channels = 4  # Always RGBA after conversion
        
        # Flatten the pixel array
        pixels_flat = pixels.reshape(-1)
        
        # Encode to QOI
        encoded = self.encode(pixels_flat, width, height, channels, colorspace)
        
        if encoded is None:
            return 0
        
        # Write to file
        with open(output_path, 'wb') as f:
            f.write(encoded)
        
        return len(encoded)
    
    def encode(self, pixels: np.ndarray, width: int, height: int, channels: int, colorspace: int) -> Optional[bytes]:
        """Encode raw pixel data to QOI format."""
        if (width == 0 or height == 0 or 
            channels < 3 or channels > 4 or 
            colorspace > 1 or 
            height >= QOI_PIXELS_MAX // width):
            return None
        
        # Calculate required size and ensure buffer is large enough
        px_len = width * height * channels
        max_size = px_len + px_len // 2 + QOI_HEADER_SIZE + 8
        
        if len(self._output_buffer) < max_size:
            self._output_buffer = bytearray(max_size)
        
        # Use memoryview for zero-copy operations
        output = memoryview(self._output_buffer)
        out_pos = 0
        
        # Write header directly
        output[out_pos:out_pos+4] = QOI_MAGIC
        out_pos += 4
        struct.pack_into('>II', output, out_pos, width, height)
        out_pos += 8
        output[out_pos] = channels
        output[out_pos + 1] = colorspace
        out_pos += 2
        
        # Initialize encoder state using flat array for index
        index = self._index_buffer
        for i in range(256):
            index[i] = 0 if i % 4 != 3 else 255
        
        px_prev_r = 0
        px_prev_g = 0
        px_prev_b = 0
        px_prev_a = 255
        run = 0
        
        # Direct pixel access for better performance
        pixels_data = pixels.data
        px_end = px_len - channels
        
        # Main encoding loop - unrolled and optimized
        px_pos = 0
        while px_pos < px_len:
            # Get current pixel values directly
            px_r = pixels_data[px_pos]
            px_g = pixels_data[px_pos + 1]
            px_b = pixels_data[px_pos + 2]
            px_a = pixels_data[px_pos + 3] if channels == 4 else 255
            
            # Check for run
            if px_r == px_prev_r and px_g == px_prev_g and px_b == px_prev_b and px_a == px_prev_a:
                run += 1
                if run == 62 or px_pos == px_end:
                    output[out_pos] = QOI_OP_RUN | (run - 1)
                    out_pos += 1
                    run = 0
            else:
                if run > 0:
                    output[out_pos] = QOI_OP_RUN | (run - 1)
                    out_pos += 1
                    run = 0
                
                # Calculate hash and index position
                hash_val = (px_r * 3 + px_g * 5 + px_b * 7 + px_a * 11) & 63
                index_pos = hash_val << 2  # hash_val * 4
                
                # Check index
                if (index[index_pos] == px_r and 
                    index[index_pos + 1] == px_g and 
                    index[index_pos + 2] == px_b and 
                    index[index_pos + 3] == px_a):
                    output[out_pos] = QOI_OP_INDEX | hash_val
                    out_pos += 1
                else:
                    # Update index
                    index[index_pos] = px_r
                    index[index_pos + 1] = px_g
                    index[index_pos + 2] = px_b
                    index[index_pos + 3] = px_a
                    
                    if px_a == px_prev_a:  # Same alpha
                        # Calculate differences
                        vr = px_r - px_prev_r
                        vg = px_g - px_prev_g
                        vb = px_b - px_prev_b
                        
                        vg_r = vr - vg
                        vg_b = vb - vg
                        
                        if -2 <= vr <= 1 and -2 <= vg <= 1 and -2 <= vb <= 1:
                            # Encode as DIFF
                            output[out_pos] = QOI_OP_DIFF | ((vr + 2) << 4) | ((vg + 2) << 2) | (vb + 2)
                            out_pos += 1
                        elif -32 <= vg <= 31 and -8 <= vg_r <= 7 and -8 <= vg_b <= 7:
                            # Encode as LUMA
                            output[out_pos] = QOI_OP_LUMA | ((vg + 32) & 0x3f)
                            output[out_pos + 1] = (((vg_r + 8) & 0x0f) << 4) | ((vg_b + 8) & 0x0f)
                            out_pos += 2
                        else:
                            # Encode as RGB
                            output[out_pos] = QOI_OP_RGB
                            output[out_pos + 1] = px_r
                            output[out_pos + 2] = px_g
                            output[out_pos + 3] = px_b
                            out_pos += 4
                    else:
                        # Encode as RGBA
                        output[out_pos] = QOI_OP_RGBA
                        output[out_pos + 1] = px_r
                        output[out_pos + 2] = px_g
                        output[out_pos + 3] = px_b
                        output[out_pos + 4] = px_a
                        out_pos += 5
                
                px_prev_r = px_r
                px_prev_g = px_g
                px_prev_b = px_b
                px_prev_a = px_a
            
            px_pos += channels
        
        # Add padding
        output[out_pos:out_pos+8] = self.padding
        out_pos += 8
        
        return bytes(output[:out_pos])
    
    def decode_file(self, input_path: str, output_path: str, force_channels: int = 0) -> bool:
        """Decode a QOI image to PNG format."""
        try:
            with open(input_path, 'rb') as f:
                data = f.read()
            
            decoded, width, height, channels, colorspace = self.decode(data, force_channels)
            
            if decoded is None:
                return False
            
            # Create PIL image directly from array
            if force_channels > 0:
                channels = force_channels
            
            decoded_array = np.frombuffer(decoded, dtype=np.uint8)
            pixels = decoded_array.reshape(height, width, channels)
            
            # Create PIL image
            if channels == 3:
                img = Image.fromarray(pixels, 'RGB')
            else:
                img = Image.fromarray(pixels, 'RGBA')
            
            # Save as PNG
            img.save(output_path, 'PNG')
            return True
            
        except Exception as e:
            print(f"Error decoding QOI: {e}")
            return False
    
    def decode(self, data: bytes, channels: int = 0) -> Tuple[Optional[bytes], int, int, int, int]:
        """Decode QOI data to raw pixels."""
        if len(data) < QOI_HEADER_SIZE + len(self.padding):
            return None, 0, 0, 0, 0
        
        # Use memoryview for zero-copy access
        data_view = memoryview(data)
        
        # Read header
        if data_view[0:4] != QOI_MAGIC:
            return None, 0, 0, 0, 0
        
        width, height = struct.unpack_from('>II', data_view, 4)
        desc_channels = data_view[12]
        colorspace = data_view[13]
        
        if (width == 0 or height == 0 or 
            desc_channels < 3 or desc_channels > 4 or 
            colorspace > 1 or
            height >= QOI_PIXELS_MAX // width):
            return None, 0, 0, 0, 0
        
        if channels == 0:
            channels = desc_channels
        
        px_len = width * height * channels
        
        # Use array.array for better performance than list
        pixels = array.array('B')
        pixels_append = pixels.extend  # Cache method lookup
        
        # Pre-allocate approximate size to avoid resizing
        try:
            pixels = array.array('B', bytes(px_len))
            pixels_ptr = 0
            use_array_index = True
        except:
            pixels = array.array('B')
            use_array_index = False
        
        # Initialize decoder state with flat array
        index = self._index_buffer
        for i in range(256):
            index[i] = 0 if i % 4 != 3 else 255
        
        px_r = 0
        px_g = 0
        px_b = 0
        px_a = 255
        run = 0
        
        chunks_len = len(data) - len(self.padding)
        p = QOI_HEADER_SIZE
        
        # Optimized decode loop
        for px_pos in range(0, px_len, channels):
            if run > 0:
                run -= 1
            elif p < chunks_len:
                b1 = data_view[p]
                p += 1
                
                if b1 == QOI_OP_RGB:
                    px_r = data_view[p]
                    px_g = data_view[p + 1]
                    px_b = data_view[p + 2]
                    p += 3
                elif b1 == QOI_OP_RGBA:
                    px_r = data_view[p]
                    px_g = data_view[p + 1]
                    px_b = data_view[p + 2]
                    px_a = data_view[p + 3]
                    p += 4
                elif (b1 & QOI_MASK_2) == QOI_OP_INDEX:
                    idx = (b1 & 0x3f) << 2
                    px_r = index[idx]
                    px_g = index[idx + 1]
                    px_b = index[idx + 2]
                    px_a = index[idx + 3]
                elif (b1 & QOI_MASK_2) == QOI_OP_DIFF:
                    px_r = (px_r + ((b1 >> 4) & 0x03) - 2) & 0xff
                    px_g = (px_g + ((b1 >> 2) & 0x03) - 2) & 0xff
                    px_b = (px_b + (b1 & 0x03) - 2) & 0xff
                elif (b1 & QOI_MASK_2) == QOI_OP_LUMA:
                    b2 = data_view[p]
                    p += 1
                    vg = (b1 & 0x3f) - 32
                    px_r = (px_r + vg - 8 + ((b2 >> 4) & 0x0f)) & 0xff
                    px_g = (px_g + vg) & 0xff
                    px_b = (px_b + vg - 8 + (b2 & 0x0f)) & 0xff
                elif (b1 & QOI_MASK_2) == QOI_OP_RUN:
                    run = (b1 & 0x3f)
                
                # Update index
                hash_val = (px_r * 3 + px_g * 5 + px_b * 7 + px_a * 11) & 63
                idx = hash_val << 2
                index[idx] = px_r
                index[idx + 1] = px_g
                index[idx + 2] = px_b
                index[idx + 3] = px_a
            
            # Add pixel to output
            if use_array_index:
                if channels == 4:
                    pixels[pixels_ptr] = px_r
                    pixels[pixels_ptr + 1] = px_g
                    pixels[pixels_ptr + 2] = px_b
                    pixels[pixels_ptr + 3] = px_a
                else:
                    pixels[pixels_ptr] = px_r
                    pixels[pixels_ptr + 1] = px_g
                    pixels[pixels_ptr + 2] = px_b
                pixels_ptr += channels
            else:
                if channels == 4:
                    pixels_append((px_r, px_g, px_b, px_a))
                else:
                    pixels_append((px_r, px_g, px_b))
        
        return pixels.tobytes(), width, height, desc_channels, colorspace


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
