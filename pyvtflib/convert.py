"""Conversion between RGBA8888 and the VTF image formats pyvtflib supports.

Uncompressed conversions are done with vectorised slice assignment
(no per-pixel Python loops) wherever possible for speed; DXT1/3/5 use
the codec in :mod:`pyvtflib.dxt`.
"""
from .formats import ImageFormat
from . import dxt as _dxt

_SUPPORTED = frozenset((
    ImageFormat.RGBA8888, ImageFormat.BGRA8888, ImageFormat.ARGB8888,
    ImageFormat.ABGR8888, ImageFormat.BGRX8888, ImageFormat.RGB888,
    ImageFormat.BGR888, ImageFormat.I8, ImageFormat.IA88, ImageFormat.A8,
    ImageFormat.RGB565, ImageFormat.BGR565, ImageFormat.DXT1,
    ImageFormat.DXT1_ONEBITALPHA, ImageFormat.DXT3, ImageFormat.DXT5,
))


def is_supported(fmt):
    return ImageFormat(fmt) in _SUPPORTED


def to_rgba8888(data, width, height, fmt):
    fmt = ImageFormat(fmt)
    if fmt == ImageFormat.RGBA8888:
        return bytes(data)
    if fmt == ImageFormat.BGRA8888:
        b = bytearray(data)
        b[0::4], b[2::4] = bytes(b[2::4]), bytes(b[0::4])
        return bytes(b)
    if fmt == ImageFormat.ARGB8888:
        out = bytearray(len(data))
        out[0::4], out[1::4], out[2::4], out[3::4] = data[1::4], data[2::4], data[3::4], data[0::4]
        return bytes(out)
    if fmt == ImageFormat.ABGR8888:
        out = bytearray(len(data))
        out[0::4], out[1::4], out[2::4], out[3::4] = data[3::4], data[2::4], data[1::4], data[0::4]
        return bytes(out)
    if fmt == ImageFormat.BGRX8888:
        n = len(data) // 4
        out = bytearray(len(data))
        out[0::4], out[1::4], out[2::4] = data[2::4], data[1::4], data[0::4]
        out[3::4] = b'\xff' * n
        return bytes(out)
    if fmt == ImageFormat.RGB888:
        n = len(data) // 3
        out = bytearray(n * 4)
        out[0::4], out[1::4], out[2::4] = data[0::3], data[1::3], data[2::3]
        out[3::4] = b'\xff' * n
        return bytes(out)
    if fmt == ImageFormat.BGR888:
        n = len(data) // 3
        out = bytearray(n * 4)
        out[0::4], out[1::4], out[2::4] = data[2::3], data[1::3], data[0::3]
        out[3::4] = b'\xff' * n
        return bytes(out)
    if fmt == ImageFormat.I8:
        out = bytearray(len(data) * 4)
        out[0::4] = out[1::4] = out[2::4] = data
        out[3::4] = b'\xff' * len(data)
        return bytes(out)
    if fmt == ImageFormat.IA88:
        n = len(data) // 2
        lum, a = data[0::2], data[1::2]
        out = bytearray(n * 4)
        out[0::4] = out[1::4] = out[2::4] = lum
        out[3::4] = a
        return bytes(out)
    if fmt == ImageFormat.A8:
        n = len(data)
        out = bytearray(n * 4)
        out[3::4] = data
        return bytes(out)
    if fmt in (ImageFormat.RGB565, ImageFormat.BGR565):
        n = len(data) // 2
        out = bytearray(n * 4)
        for i in range(n):
            v = data[2 * i] | (data[2 * i + 1] << 8)
            c0, c1, c2 = (v >> 11) & 0x1F, (v >> 5) & 0x3F, v & 0x1F
            r, g, b = (c0 << 3) | (c0 >> 2), (c1 << 2) | (c1 >> 4), (c2 << 3) | (c2 >> 2)
            if fmt == ImageFormat.BGR565:
                r, b = b, r
            o = i * 4
            out[o], out[o + 1], out[o + 2], out[o + 3] = r, g, b, 255
        return bytes(out)
    if fmt in (ImageFormat.DXT1, ImageFormat.DXT1_ONEBITALPHA):
        return _dxt.decode_dxt1(data, width, height)
    if fmt == ImageFormat.DXT3:
        return _dxt.decode_dxt3(data, width, height)
    if fmt == ImageFormat.DXT5:
        return _dxt.decode_dxt5(data, width, height)
    raise NotImplementedError(f"conversion from {fmt.name} is not supported")


def from_rgba8888(rgba, width, height, fmt):
    fmt = ImageFormat(fmt)
    if fmt == ImageFormat.RGBA8888:
        return bytes(rgba)
    if fmt == ImageFormat.BGRA8888:
        b = bytearray(rgba)
        b[0::4], b[2::4] = bytes(b[2::4]), bytes(b[0::4])
        return bytes(b)
    if fmt == ImageFormat.ARGB8888:
        out = bytearray(len(rgba))
        out[1::4], out[2::4], out[3::4], out[0::4] = rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4]
        return bytes(out)
    if fmt == ImageFormat.ABGR8888:
        out = bytearray(len(rgba))
        out[3::4], out[2::4], out[1::4], out[0::4] = rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4]
        return bytes(out)
    if fmt == ImageFormat.BGRX8888:
        n = len(rgba) // 4
        out = bytearray(len(rgba))
        out[2::4], out[1::4], out[0::4] = rgba[0::4], rgba[1::4], rgba[2::4]
        out[3::4] = b'\xff' * n
        return bytes(out)
    if fmt == ImageFormat.RGB888:
        n = len(rgba) // 4
        out = bytearray(n * 3)
        out[0::3], out[1::3], out[2::3] = rgba[0::4], rgba[1::4], rgba[2::4]
        return bytes(out)
    if fmt == ImageFormat.BGR888:
        n = len(rgba) // 4
        out = bytearray(n * 3)
        out[0::3], out[1::3], out[2::3] = rgba[2::4], rgba[1::4], rgba[0::4]
        return bytes(out)
    if fmt == ImageFormat.I8:
        n = len(rgba) // 4
        r, g, b = rgba[0::4], rgba[1::4], rgba[2::4]
        return bytes(((r[i] * 77 + g[i] * 151 + b[i] * 28) >> 8) for i in range(n))
    if fmt == ImageFormat.IA88:
        n = len(rgba) // 4
        r, g, b, a = rgba[0::4], rgba[1::4], rgba[2::4], rgba[3::4]
        out = bytearray(n * 2)
        for i in range(n):
            out[2 * i] = (r[i] * 77 + g[i] * 151 + b[i] * 28) >> 8
            out[2 * i + 1] = a[i]
        return bytes(out)
    if fmt == ImageFormat.A8:
        return bytes(rgba[3::4])
    if fmt in (ImageFormat.RGB565, ImageFormat.BGR565):
        n = len(rgba) // 4
        out = bytearray(n * 2)
        for i in range(n):
            o = i * 4
            r, g, b = rgba[o], rgba[o + 1], rgba[o + 2]
            if fmt == ImageFormat.BGR565:
                r, b = b, r
            v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
            out[2 * i], out[2 * i + 1] = v & 0xFF, (v >> 8) & 0xFF
        return bytes(out)
    if fmt in (ImageFormat.DXT1, ImageFormat.DXT1_ONEBITALPHA):
        return _dxt.encode_dxt1(rgba, width, height)
    if fmt == ImageFormat.DXT3:
        return _dxt.encode_dxt3(rgba, width, height)
    if fmt == ImageFormat.DXT5:
        return _dxt.encode_dxt5(rgba, width, height)
    raise NotImplementedError(f"conversion to {fmt.name} is not supported")


def convert(data, width, height, src_fmt, dst_fmt):
    """Convert raw pixel data directly between any two supported formats."""
    if ImageFormat(src_fmt) == ImageFormat(dst_fmt):
        return bytes(data)
    return from_rgba8888(to_rgba8888(data, width, height, src_fmt), width, height, dst_fmt)
