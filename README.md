# 👑 QOI-Py - The QOIEEN of Python Image Compression

![Python](https://img.shields.io/badge/python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![QOI](https://img.shields.io/badge/QOI-spec%20compliant-orange.svg)
![Sass](https://img.shields.io/badge/sass-100%25-pink.svg)

A fiercely optimized, pure Python implementation of the [QOI (Quite OK Image)](https://qoiformat.org/) format. We took a "Quite OK" format and gave her a BBL (Byte-Buffer Logic) and a face lift.

## 🤷‍♂️ What is QOI?

QOI is a fast, lossless image compression format that fits on a single napkin. It's designed to be:
- **Fast** - Like, C++ fast (usually).
- **Simple** - Easier to understand than your ex's mixed signals.
- **Lossless** - Your pixels come out exactly as they went in. No filters, #NoFilter.
- **"Quite OK"** - She's not trying to be JPEG 2000, she's just trying to get the job done.

## 💅 The Glow Up (Features)

This isn't your average "for loop" implementation. We optimized her to within an inch of her interpreter's life.

- ✅ **Full QOI Spec Compliance**: She follows the rules, mostly.
- ✅ **Zero Heavy Dependencies**: We kicked `numpy` out of the house. We don't need her drama. It's just Python and `Pillow` for file I/O.
- ✅ **Memory Aware**: We use `memoryview` because we hate copying data. Only recycled references in this household.
- ✅ **RGB & RGBA**: She handles transparency like a pro.
- ✅ **Certified "Good Enough"**: It's Python doing low-level bit shifting. It's camp.

## 📦 Installation

```bash
# Clone the castle
git clone https://github.com/reedmayhew18/qoi-py.git
cd qoi-py

# Install dependencies (literally just Pillow, we travel light)
pip install pillow
```

## 🚀 Usage

### Command Line Runway

```bash
# Squeeze that PNG into a QOI
python qoi.py image.png
# Output: image.qoi (She's skinny now!)

# Inflate the QOI back to PNG
python qoi.py image.qoi
# Output: image.png
```

### Python API

```python
from qoi import QOICodec

# Initialize her majesty
codec = QOICodec()

# Encode
bytes_written = codec.encode_file('input.png', 'output.qoi')
print(f"Slayed {bytes_written} bytes")

# Decode
success = codec.decode_file('input.qoi', 'output.png')
print(f"Resurrection {'successful' if success else 'flopped'}")
```

## 👠 Performance

Look, she's running in heels (the Python Interpreter).

We manually unrolled loops, cached local variables, banished dot-operators, and used raw byte indexing instead of slicing. She is as fast as pure Python *physically allows*.

- **Encoding**: faster than a snail, slower than C. It's "contemplative."
- **Decoding**: Actually surprisingly snappy. She puts the "Quite" in "Quite OK."
- **Memory**: Snatched waist. We pre-allocate buffers so the garbage collector can take a nap.

**Benchmarks:**
*"She's serving face, not frame rate."*
- **512x512 RGB**: ~0.4s (She's sprinting)
- **1920x1080 RGBA**: ~2.0s (She's jogging, don't rush her)

## 🔧 Implementation Tea

How did we make Python do this?
1.  **Local Variable Caching**: Because looking up `self.variable` takes too long, sweetie.
2.  **No Slicing**: Slicing creates copies. We don't litter. We index raw bytes.
3.  **Bitwise Magic**: We use `& 63` instead of `% 64` because math is hard but logic is fashion.
4.  **Lists over Arrays**: We switched from `array.array` to standard lists for the hash index because CPython optimizes lists like crazy.

## 🤝 Contributing

Think you can make her tighter? Want to optimize a loop? Feel free to submit a PR!
- Bug fixes: Yes.
- Optimization hacks: **YES PLEASE.**
- Formatting complaints: The door is over there.

## 📝 License

MIT License - Because style should be free.

## 🙏 Acknowledgments

- [Dominic Szablewski](https://phoboslab.org/) for inventing QOI.
- The Python Core Developers for creating a language that is slow but beautiful.
- My anxiety, for making me optimize this at 3 AM.

## ⚠️ Disclaimer

**This is a Python script doing binary compression.**

Do not use this for:
- Real-time video streaming.
- Life support systems.
- Impressing C++ developers (they won't get it).

Do use this for:
- Learning how compression works.
- Proving that Python can do anything if you bully it enough.
- The aesthetic.

---

*Remember: It's not about the execution speed, it's about the developer experience. And this experience was ✨ traumatic ✨.*
