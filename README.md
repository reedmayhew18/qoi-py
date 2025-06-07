# QOI-Py - A Poorly Implemented Native Python QOI Encoder/Decoder

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![QOI](https://img.shields.io/badge/QOI-spec%20compliant-orange.svg)

A questionably optimized, pure Python implementation of the [QOI (Quite OK Image)](https://qoiformat.org/) format encoder and decoder. Because sometimes you need image compression that's just... quite OK.

## 🤷‍♂️ What is QOI?

QOI (Quite OK Image) is a fast, lossless image compression format that achieves compression ratios comparable to PNG while being significantly simpler to implement. It's designed to be:
- **Fast** - Encoding/decoding speeds that leave PNG in the dust
- **Simple** - The entire spec fits on a single page
- **Lossless** - Your pixels come out exactly as they went in
- **"Quite OK"** - Not the best at everything, but good enough for most things

## 🎯 Features

- ✅ Full QOI specification compliance (probably)
- ✅ Encode PNG/JPEG images to QOI format
- ✅ Decode QOI images back to PNG
- ✅ Support for RGB and RGBA images
- ✅ Poorly optimized for that authentic Python experience
- ✅ Zero external dependencies (except NumPy and Pillow, but who's counting?)

## 📦 Installation

```bash
# Clone this repository
git clone https://github.com/reedmayhew18/qoi-py.git
cd qoi-py

# Install dependencies
pip install numpy pillow
```

## 🚀 Usage

### Command Line Interface

```bash
# Convert PNG/JPEG to QOI
python qoi.py image.png
# Output: image.qoi

# Convert QOI back to PNG
python qoi.py image.qoi
# Output: image.png
```

### Python API

```python
from qoi import QOICodec

# Initialize codec
codec = QOICodec()

# Encode PNG/JPEG to QOI
bytes_written = codec.encode_file('input.png', 'output.qoi')
print(f"Encoded {bytes_written} bytes")

# Decode QOI to PNG
success = codec.decode_file('input.qoi', 'output.png')
print(f"Decode {'successful' if success else 'failed'}")
```

### Advanced Usage

```python
import numpy as np
from qoi import QOICodec

codec = QOICodec()

# Work with raw pixel data
pixels = np.random.randint(0, 255, (100, 100, 4), dtype=np.uint8)
encoded = codec.encode(pixels.flatten(), width=100, height=100, channels=4, colorspace=0)

# Decode back
decoded, w, h, c, cs = codec.decode(encoded)
```

## 🐌 Performance

This implementation is "poorly optimized" in the most endearing way possible. While we've made some attempts at optimization (pre-allocated buffers, bitwise operations, etc.), it's still Python, so expect:

- **Encoding speed**: Slower than C implementations, faster than a snail
- **Decoding speed**: Quick enough to not make you question your life choices
- **Memory usage**: Reasonable, unless you're processing billboard-sized images

## 🔧 Implementation Details

### Optimizations (Such As They Are)
- Pre-allocated buffers to reduce memory allocation overhead
- Bitwise operations for hash calculations
- Direct memory access using memoryview
- Flat arrays instead of nested structures
- array.array for typed data instead of Python lists

### Supported Features
- ✅ QOI_OP_RGB - Full color pixels
- ✅ QOI_OP_RGBA - Full color with alpha
- ✅ QOI_OP_INDEX - Previously seen colors
- ✅ QOI_OP_DIFF - Small differences
- ✅ QOI_OP_LUMA - Larger differences
- ✅ QOI_OP_RUN - Repeated pixels

## 📊 Benchmarks

*"It's not slow, it's contemplative."*

Typical performance on a modern machine:
- **512x512 RGB image**: ~50ms encoding, ~30ms decoding
- **1920x1080 RGBA image**: ~400ms encoding, ~250ms decoding
- **Your patience**: Tested, but not broken

## 🤝 Contributing

Found a way to make this implementation even more poorly optimized? Or perhaps (gasp) better? Feel free to submit a PR! We welcome:
- Bug fixes (there are probably many)
- Performance "improvements" 
- Additional features nobody asked for
- More sarcastic comments in the code

## 📝 License

MIT License - Because even poorly implemented code deserves freedom.

## 🙏 Acknowledgments

- [Dominic Szablewski](https://phoboslab.org/) for creating the QOI format
- The Python community for enabling our questionable life choices
- Coffee, for making this implementation possible

## ⚠️ Disclaimer

This implementation is called "poorly implemented" for a reason. While it correctly implements the QOI specification (we think), it's not recommended for:
- Production use (unless you enjoy living dangerously)
- Performance-critical applications
- Impressing your friends who write C

It IS recommended for:
- Learning how QOI works
- Quick and dirty image conversion
- Proving that anything can be implemented in Python

## 🐛 Known Issues

- It's written in Python (some consider this a bug, we consider it a feature)
- Probably doesn't handle edge cases you haven't thought of yet
- May cause existential questions about why you're not using a C implementation

---

*Remember: It's not about the destination, it's about the journey. And this journey involves pure Python image compression.*
```