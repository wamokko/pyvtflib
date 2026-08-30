"""Minimal, dependency-free DXT1 / DXT3 / DXT5 block codec.

Decoding is exact (standard BC1-3 math). Encoding uses a fast min/max
box-fit endpoint selection (good quality/speed trade-off, no external
compressor required -- the original VTFLib relied on nVidia's nvDXTlib
for this, which pyvtflib intentionally does not depend on).
"""
import struct


def _unpack565(v):
    r = (v >> 11) & 0x1F
    g = (v >> 5) & 0x3F
    b = v & 0x1F
    return (r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)


def _pack565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


# ---------------------------------------------------------------- decoding --

def decode_dxt1(data, width, height):
    out = bytearray(width * height * 4)
    pos = 0
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            c0, c1, bits = struct.unpack_from('<HHI', data, pos)
            pos += 8
            r0, g0, b0 = _unpack565(c0)
            r1, g1, b1 = _unpack565(c1)
            if c0 > c1:
                pal = [
                    (r0, g0, b0, 255), (r1, g1, b1, 255),
                    ((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3, 255),
                    ((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3, 255),
                ]
            else:
                pal = [
                    (r0, g0, b0, 255), (r1, g1, b1, 255),
                    ((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255),
                    (0, 0, 0, 0),
                ]
            for j in range(4):
                yy = by + j
                if yy >= height:
                    continue
                row = (bits >> (8 * j)) & 0xFF
                for i in range(4):
                    xx = bx + i
                    if xx >= width:
                        continue
                    r, g, b, a = pal[(row >> (2 * i)) & 3]
                    o = (yy * width + xx) * 4
                    out[o] = r; out[o + 1] = g; out[o + 2] = b; out[o + 3] = a
    return bytes(out)


def decode_dxt3(data, width, height):
    out = bytearray(width * height * 4)
    pos = 0
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            arows = struct.unpack_from('<4H', data, pos)
            pos += 8
            c0, c1, bits = struct.unpack_from('<HHI', data, pos)
            pos += 8
            r0, g0, b0 = _unpack565(c0)
            r1, g1, b1 = _unpack565(c1)
            pal = [
                (r0, g0, b0), (r1, g1, b1),
                ((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3),
                ((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3),
            ]
            for j in range(4):
                yy = by + j
                if yy >= height:
                    continue
                row = (bits >> (8 * j)) & 0xFF
                arow = arows[j]
                for i in range(4):
                    xx = bx + i
                    if xx >= width:
                        continue
                    a4 = (arow >> (4 * i)) & 0xF
                    r, g, b = pal[(row >> (2 * i)) & 3]
                    o = (yy * width + xx) * 4
                    out[o] = r; out[o + 1] = g; out[o + 2] = b
                    out[o + 3] = (a4 << 4) | a4
    return bytes(out)


def decode_dxt5(data, width, height):
    out = bytearray(width * height * 4)
    pos = 0
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            a0, a1 = data[pos], data[pos + 1]
            abits = int.from_bytes(data[pos + 2:pos + 8], 'little')
            pos += 8
            c0, c1, bits = struct.unpack_from('<HHI', data, pos)
            pos += 8
            if a0 > a1:
                atab = (a0, a1,
                        (6 * a0 + 1 * a1) // 7, (5 * a0 + 2 * a1) // 7,
                        (4 * a0 + 3 * a1) // 7, (3 * a0 + 4 * a1) // 7,
                        (2 * a0 + 5 * a1) // 7, (1 * a0 + 6 * a1) // 7)
            else:
                atab = (a0, a1,
                        (4 * a0 + 1 * a1) // 5, (3 * a0 + 2 * a1) // 5,
                        (2 * a0 + 3 * a1) // 5, (1 * a0 + 4 * a1) // 5, 0, 255)
            r0, g0, b0 = _unpack565(c0)
            r1, g1, b1 = _unpack565(c1)
            pal = [
                (r0, g0, b0), (r1, g1, b1),
                ((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3),
                ((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3),
            ]
            for j in range(4):
                yy = by + j
                if yy >= height:
                    continue
                row = (bits >> (8 * j)) & 0xFF
                for i in range(4):
                    xx = bx + i
                    if xx >= width:
                        continue
                    idx = j * 4 + i
                    asel = (abits >> (3 * idx)) & 7
                    r, g, b = pal[(row >> (2 * i)) & 3]
                    o = (yy * width + xx) * 4
                    out[o] = r; out[o + 1] = g; out[o + 2] = b; out[o + 3] = atab[asel]
    return bytes(out)


# ---------------------------------------------------------------- encoding --

def _block_pixels(rgba, width, height, bx, by):
    px = []
    for j in range(4):
        yy = by + j if by + j < height else height - 1
        row = (yy * width) * 4
        for i in range(4):
            xx = bx + i if bx + i < width else width - 1
            o = row + xx * 4
            px.append(rgba[o:o + 4])
    return px

def _color_block(px):
    rs = [p[0] for p in px]; gs = [p[1] for p in px]; bs = [p[2] for p in px]
    rmax, gmax, bmax = max(rs), max(gs), max(bs)
    rmin, gmin, bmin = min(rs), min(gs), min(bs)
    c0 = _pack565(rmax, gmax, bmax)
    c1 = _pack565(rmin, gmin, bmin)
    if c0 < c1:
        c0, c1 = c1, c0
    r0, g0, b0 = _unpack565(c0)
    r1, g1, b1 = _unpack565(c1)
    pal = ((r0, g0, b0), (r1, g1, b1),
           ((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3),
           ((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3))
    bits = 0
    for idx, p in enumerate(px):
        best, best_d = 0, 1 << 30
        for k, pc in enumerate(pal):
            d = (p[0] - pc[0]) ** 2 + (p[1] - pc[1]) ** 2 + (p[2] - pc[2]) ** 2
            if d < best_d:
                best_d, best = d, k
        bits |= best << (2 * idx)
    return c0, c1, bits


def encode_dxt1(rgba, width, height):
    out = bytearray()
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            c0, c1, bits = _color_block(_block_pixels(rgba, width, height, bx, by))
            out += struct.pack('<HHI', c0, c1, bits)
    return bytes(out)


def encode_dxt3(rgba, width, height):
    out = bytearray()
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            px = _block_pixels(rgba, width, height, bx, by)
            arows = []
            for j in range(4):
                packed = 0
                for i in range(4):
                    packed |= (px[j * 4 + i][3] >> 4) << (4 * i)
                arows.append(packed)
            c0, c1, bits = _color_block(px)
            out += struct.pack('<4H', *arows)
            out += struct.pack('<HHI', c0, c1, bits)
    return bytes(out)


def encode_dxt5(rgba, width, height):
    out = bytearray()
    for by in range(0, height, 4):
        for bx in range(0, width, 4):
            px = _block_pixels(rgba, width, height, bx, by)
            alphas = [p[3] for p in px]
            a0, a1 = max(alphas), min(alphas)
            if a0 == a1:
                atab = (a0,) * 8
            elif a0 > a1:
                atab = (a0, a1,
                        (6 * a0 + 1 * a1) // 7, (5 * a0 + 2 * a1) // 7,
                        (4 * a0 + 3 * a1) // 7, (3 * a0 + 4 * a1) // 7,
                        (2 * a0 + 5 * a1) // 7, (1 * a0 + 6 * a1) // 7)
            else:
                atab = (a0, a1,
                        (4 * a0 + 1 * a1) // 5, (3 * a0 + 2 * a1) // 5,
                        (2 * a0 + 3 * a1) // 5, (1 * a0 + 4 * a1) // 5, 0, 255)
            abits = 0
            for idx, a in enumerate(alphas):
                best, best_d = 0, 1 << 30
                for k, av in enumerate(atab):
                    d = a - av
                    d = d if d >= 0 else -d
                    if d < best_d:
                        best_d, best = d, k
                abits |= best << (3 * idx)
            c0, c1, bits = _color_block(px)
            out += bytes((a0, a1)) + abits.to_bytes(6, 'little')
            out += struct.pack('<HHI', c0, c1, bits)
    return bytes(out)
