# pyvtflib

A pure-Python, **zero-dependency** functional rewrite of [VTFLib](https://github.com/panzi/VTFLib)
for reading and writing Valve's **VTF** (texture) and **VMT** (material) file
formats. Works identically on Windows, Linux and macOS — there is no native
code, no `ctypes`, no compiled extension, and no third-party packages
required (not even Pillow/NumPy). Just `import pyvtflib` and go.

## Install

Copy the `pyvtflib/` folder into your project, or install it:

```bash
pip install .
```

## Quick start

### Textures (VTF)

```python
from pyvtflib import VTFFile, ImageFormat

# Load
tex = VTFFile.load("example.vtf")
print(tex.width, tex.height, tex.image_format.name, tex.mip_count)

rgba = tex.get_rgba()                 # decoded RGBA8888 bytes, mip 0
thumb = tex.get_thumbnail_rgba()      # decoded low-res thumbnail, or None

# Modify a mip level and re-save
tex.set_rgba(rgba, mip=0)
tex.save("copy.vtf")

# Create a brand-new texture from raw RGBA8888 pixel data
new_tex = VTFFile.create(
    width=256, height=256, rgba=rgba,
    image_format=ImageFormat.DXT5,     # compressed on the fly
    mipmaps=True, thumbnail=True,
)
new_tex.save("new.vtf")
```

`VTFFile.load` / `.save` accept a file path **or** raw `bytes`, so it is
equally easy to work with in-memory data (e.g. pulled from a VPK/pak file).

Cubemaps and animated/multi-frame textures are supported via the
`frame` / `face` / `slice_` / `mip` parameters on `get_data`, `set_data`,
`get_rgba` and `set_rgba`.

### Materials (VMT)

```python
from pyvtflib import VMTFile

mat = VMTFile.load("example.vmt")
print(mat.root.name)                       # e.g. "LightmappedGeneric"
print(mat.root["$basetexture"])            # -> "brick/brick01"

mat.root["$basetexture"] = "brick/brick02"  # edit in place
mat.root.add_string("$bumpmap", "brick/brick02_normal")

mat.save("copy.vmt")
```

`VMTFile.loads(text)` / `.dumps()` work directly on strings if you don't
need file I/O.

## Supported image formats

Decode **and** encode: `RGBA8888`, `BGRA8888`, `ARGB8888`, `ABGR8888`,
`BGRX8888`, `RGB888`, `BGR888`, `I8`, `IA88`, `A8`, `RGB565`, `BGR565`,
`DXT1`, `DXT1_ONEBITALPHA`, `DXT3`, `DXT5`.

Header versions 7.0–7.5 are all read/written correctly, including the
7.3+ resource-dictionary layout (thumbnail/image offsets, CRC/LOD/TSO/KVD
and arbitrary custom resources).

DXT encoding uses a fast min/max ("box-fit") endpoint search — good
quality for a dependency-free pure-Python encoder, though not as sharp as
a dedicated GPU/SIMD compressor. Decoding is bit-exact standard BC1/2/3
math.

## Design notes / why it's small

* **No native dependencies** — the original VTFLib links against
  `nvDXTlib` for DXT compression and mipmap generation; this rewrite
  replaces that with a small pure-Python box-filter mip chain and a
  simple pure-Python DXT encoder, so it runs anywhere Python does.
* **In-memory model** — VTF image data is kept as
  `image_mips[mip][frame][face][slice] -> bytes`, a direct, easy-to-index
  Python structure, rather than one flat byte buffer with manual pointer
  arithmetic like the C++ original. This removes an entire class of
  off-by-one bugs while still round-tripping the exact on-disk layout.
* **Vectorised where it matters** — uncompressed pixel-format conversions
  (`RGBA8888` ↔ `BGRA8888`/`RGB888`/etc.) use slice assignment instead of
  per-pixel Python loops, which is 10–50x faster than the naive approach.
* **~5 small modules, no framework** — `formats.py` (enums/sizes),
  `dxt.py` (codec), `convert.py` (pixel format conversion), `vtf.py`
  (texture container), `vmt.py` (material container). Read any one of
  them in a few minutes.

## Not (yet) implemented

Matching the original's *optional*, hardware/NV-dependent features was
intentionally left out to keep this dependency-free:
normal-map generation, sphere-map generation, and reflectivity
auto-computation. These can be added on top using `get_rgba()` /
`set_rgba()` since all pixel data is plain Python `bytes`.

## Running the self-tests

```bash
python -m pyvtflib._selftest
```
