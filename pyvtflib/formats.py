"""Image format definitions and pixel-geometry math for VTF files."""
from enum import IntEnum


class ImageFormat(IntEnum):
    RGBA8888 = 0
    ABGR8888 = 1
    RGB888 = 2
    BGR888 = 3
    RGB565 = 4
    I8 = 5
    IA88 = 6
    P8 = 7
    A8 = 8
    RGB888_BLUESCREEN = 9
    BGR888_BLUESCREEN = 10
    ARGB8888 = 11
    BGRA8888 = 12
    DXT1 = 13
    DXT3 = 14
    DXT5 = 15
    BGRX8888 = 16
    BGR565 = 17
    BGRX5551 = 18
    BGRA4444 = 19
    DXT1_ONEBITALPHA = 20
    BGRA5551 = 21
    UV88 = 22
    UVWQ8888 = 23
    RGBA16161616F = 24
    RGBA16161616 = 25
    UVLX8888 = 26
    R32F = 27
    RGB323232F = 28
    RGBA32323232F = 29
    NONE = -1


# ImageFormat -> (display name, bits/pixel, bytes/pixel, is compressed)
_INFO = {
    ImageFormat.RGBA8888: ("RGBA8888", 32, 4, False),
    ImageFormat.ABGR8888: ("ABGR8888", 32, 4, False),
    ImageFormat.RGB888: ("RGB888", 24, 3, False),
    ImageFormat.BGR888: ("BGR888", 24, 3, False),
    ImageFormat.RGB565: ("RGB565", 16, 2, False),
    ImageFormat.I8: ("I8", 8, 1, False),
    ImageFormat.IA88: ("IA88", 16, 2, False),
    ImageFormat.P8: ("P8", 8, 1, False),
    ImageFormat.A8: ("A8", 8, 1, False),
    ImageFormat.RGB888_BLUESCREEN: ("RGB888 Bluescreen", 24, 3, False),
    ImageFormat.BGR888_BLUESCREEN: ("BGR888 Bluescreen", 24, 3, False),
    ImageFormat.ARGB8888: ("ARGB8888", 32, 4, False),
    ImageFormat.BGRA8888: ("BGRA8888", 32, 4, False),
    ImageFormat.DXT1: ("DXT1", 4, 0, True),
    ImageFormat.DXT3: ("DXT3", 8, 0, True),
    ImageFormat.DXT5: ("DXT5", 8, 0, True),
    ImageFormat.BGRX8888: ("BGRX8888", 32, 4, False),
    ImageFormat.BGR565: ("BGR565", 16, 2, False),
    ImageFormat.BGRX5551: ("BGRX5551", 16, 2, False),
    ImageFormat.BGRA4444: ("BGRA4444", 16, 2, False),
    ImageFormat.DXT1_ONEBITALPHA: ("DXT1 One Bit Alpha", 4, 0, True),
    ImageFormat.BGRA5551: ("BGRA5551", 16, 2, False),
    ImageFormat.UV88: ("UV88", 16, 2, False),
    ImageFormat.UVWQ8888: ("UVWQ8888", 32, 4, False),
    ImageFormat.RGBA16161616F: ("RGBA16161616F", 64, 8, False),
    ImageFormat.RGBA16161616: ("RGBA16161616", 64, 8, False),
    ImageFormat.UVLX8888: ("UVLX8888", 32, 4, False),
    ImageFormat.R32F: ("R32F", 32, 4, False),
    ImageFormat.RGB323232F: ("RGB323232F", 96, 12, False),
    ImageFormat.RGBA32323232F: ("RGBA32323232F", 128, 16, False),
}


def format_name(fmt):
    return _INFO[ImageFormat(fmt)][0]


def is_compressed(fmt):
    return _INFO[ImageFormat(fmt)][3]


def bytes_per_pixel(fmt):
    return _INFO[ImageFormat(fmt)][2]


def compute_image_size(width, height, depth, fmt):
    """Bytes needed to store one image (all Z slices) at the given format."""
    fmt = ImageFormat(fmt)
    if fmt in (ImageFormat.DXT1, ImageFormat.DXT1_ONEBITALPHA):
        w = 4 if 0 < width < 4 else width
        h = 4 if 0 < height < 4 else height
        return ((w + 3) // 4) * ((h + 3) // 4) * 8 * depth
    if fmt in (ImageFormat.DXT3, ImageFormat.DXT5):
        w = 4 if 0 < width < 4 else width
        h = 4 if 0 < height < 4 else height
        return ((w + 3) // 4) * ((h + 3) // 4) * 16 * depth
    return width * height * depth * bytes_per_pixel(fmt)


def compute_mipmap_count(width, height, depth=1):
    """Number of mip levels from (width,height,depth) down to 1x1x1 (inclusive)."""
    count = 0
    w, h, d = width, height, depth
    while True:
        count += 1
        w >>= 1
        h >>= 1
        d >>= 1
        if w == 0 and h == 0 and d == 0:
            break
    return count


def mipmap_dimensions(width, height, depth, level):
    return max(width >> level, 1), max(height >> level, 1), max(depth >> level, 1)


def compute_mipmap_size(width, height, depth, level, fmt):
    w, h, d = mipmap_dimensions(width, height, depth, level)
    return compute_image_size(w, h, d, fmt)
