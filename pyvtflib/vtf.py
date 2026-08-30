"""VTF (Valve Texture Format) reader/writer -- pure Python, no dependencies.

Compatible with header versions 7.0 through 7.5 (resource-dictionary
aware). Image data is kept in memory as nested lists indexed
``[mip][frame][face][slice]`` -> ``bytes`` in the texture's native
on-disk pixel format, which keeps the implementation simple while
staying fully compatible with the real file layout on save.
"""
import struct
from collections import OrderedDict

from .formats import (
    ImageFormat, compute_image_size, compute_mipmap_count,
    mipmap_dimensions, compute_mipmap_size,
)
from . import convert as _convert

VTF_MAJOR_VERSION = 7
VTF_MINOR_VERSION = 5


class VTFFlags:
    POINTSAMPLE = 0x00000001
    TRILINEAR = 0x00000002
    CLAMPS = 0x00000004
    CLAMPT = 0x00000008
    ANISOTROPIC = 0x00000010
    HINT_DXT5 = 0x00000020
    SRGB = 0x00000040
    NORMAL = 0x00000080
    NOMIP = 0x00000100
    NOLOD = 0x00000200
    MINMIP = 0x00000400
    PROCEDURAL = 0x00000800
    ONEBITALPHA = 0x00001000
    EIGHTBITALPHA = 0x00002000
    ENVMAP = 0x00004000
    RENDERTARGET = 0x00008000
    NODEBUGOVERRIDE = 0x00020000
    SINGLECOPY = 0x00040000
    NODEPTHBUFFER = 0x00800000
    CLAMPU = 0x02000000
    VERTEXTEXTURE = 0x04000000
    SSBUMP = 0x08000000
    BORDER = 0x20000000


class VTFResourceType:
    LOW_RES_IMAGE = 0x01
    IMAGE = 0x30
    SHEET = 0x10
    CRC = ord('C') | (ord('R') << 8) | (ord('C') << 16) | (0x02 << 24)
    LOD = ord('L') | (ord('O') << 8) | (ord('D') << 16) | (0x02 << 24)
    TSO = ord('T') | (ord('S') << 8) | (ord('O') << 16) | (0x02 << 24)
    KVD = ord('K') | (ord('V') << 8) | (ord('D') << 16)


_BASE_FMT = "<4s2IIHHIHH4x3f4xfiBiBB"
_BASE_SIZE = struct.calcsize(_BASE_FMT)  # 63 bytes, versions 7.0/7.1


def _align16(n):
    return (n + 15) // 16 * 16


def _resize_rgba(data, sw, sh, dw, dh):
    """Nearest-sample resize (used for downlevel mips / thumbnail)."""
    if (sw, sh) == (dw, dh):
        return bytes(data)
    out = bytearray(dw * dh * 4)
    for y in range(dh):
        sy = min(y * sh // dh, sh - 1)
        srow = sy * sw * 4
        drow = y * dw * 4
        for x in range(dw):
            sx = min(x * sw // dw, sw - 1)
            so, do = srow + sx * 4, drow + x * 4
            out[do:do + 4] = data[so:so + 4]
    return bytes(out)


def _box_downsample_rgba(data, w, h):
    """Halve image size (box filter, 2x2 average). Returns (data, nw, nh)."""
    nw, nh = max(w // 2, 1), max(h // 2, 1)
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        y0 = min(y * 2, h - 1)
        y1 = min(y * 2 + 1, h - 1)
        for x in range(nw):
            x0 = min(x * 2, w - 1)
            x1 = min(x * 2 + 1, w - 1)
            o00, o01 = (y0 * w + x0) * 4, (y0 * w + x1) * 4
            o10, o11 = (y1 * w + x0) * 4, (y1 * w + x1) * 4
            do = (y * nw + x) * 4
            for c in range(4):
                out[do + c] = (data[o00 + c] + data[o01 + c] + data[o10 + c] + data[o11 + c]) // 4
    return bytes(out), nw, nh


class VTFFile:
    """An in-memory VTF texture."""

    def __init__(self):
        self.version = (7, 4)
        self.width = 0
        self.height = 0
        self.depth = 1
        self.frames = 1
        self.faces = 1
        self.flags = 0
        self.start_frame = 0
        self.reflectivity = (1.0, 1.0, 1.0)
        self.bump_scale = 1.0
        self.image_format = ImageFormat.RGBA8888
        self.low_res_image_format = ImageFormat.NONE
        self.low_res_image_width = 0
        self.low_res_image_height = 0
        self.thumbnail_data = b''
        self.resources = OrderedDict()          # custom resource type -> bytes
        self.image_mips = []                    # [mip][frame][face][slice] -> bytes

    # ------------------------------------------------------------ metadata --
    @property
    def mip_count(self):
        return len(self.image_mips)

    @property
    def loaded(self):
        return self.width > 0 and self.height > 0 and bool(self.image_mips)

    @property
    def is_cubemap(self):
        return bool(self.flags & VTFFlags.ENVMAP)

    def get_flag(self, flag):
        return bool(self.flags & flag)

    def set_flag(self, flag, state):
        self.flags = (self.flags | flag) if state else (self.flags & ~flag)

    # -------------------------------------------------------------- loading --
    @classmethod
    def load(cls, source, header_only=False):
        """Load a VTF from a file path, or from raw bytes."""
        if isinstance(source, (bytes, bytearray, memoryview)):
            buf = bytes(source)
        else:
            with open(source, 'rb') as f:
                buf = f.read()
        return cls._parse(buf, header_only)

    @staticmethod
    def _unpack_header(buf, header_size):
        (type_string, ver0, ver1, _hsz, width, height, flags, frames,
         start_frame, rx, ry, rz, bump_scale, image_format, mip_count,
         low_fmt, low_w, low_h) = struct.unpack_from(_BASE_FMT, buf, 0)
        if type_string[:3] != b'VTF':
            raise ValueError("not a valid VTF file (bad signature)")
        version = (ver0, ver1)
        off = _BASE_SIZE
        depth, resource_count = 1, 0
        if version >= (7, 2) and off + 2 <= header_size:
            depth, = struct.unpack_from('<H', buf, off)
            off += 2
        if version >= (7, 3) and off + 7 <= header_size:
            off += 3  # padding
            resource_count, = struct.unpack_from('<I', buf, off)
            off += 4
        # The resource directory itself starts at the 16-byte-aligned end of
        # the fixed-size header fields (matching how the writer lays it out),
        # not at the raw byte offset right after resource_count.
        resource_dir_offset = _align16(off)
        return dict(
            version=version, width=width, height=height, depth=max(depth, 1),
            flags=flags, frames=max(frames, 1), start_frame=start_frame,
            reflectivity=(rx, ry, rz), bump_scale=bump_scale,
            image_format=ImageFormat(image_format), mip_count=max(mip_count, 1),
            low_res_image_format=ImageFormat(low_fmt),
            low_res_image_width=low_w, low_res_image_height=low_h,
            resource_count=resource_count, resource_dir_offset=resource_dir_offset,
        )

    @classmethod
    def _parse(cls, buf, header_only=False):
        if len(buf) < 16 or buf[:3] != b'VTF':
            raise ValueError("not a valid VTF file")
        header_size, = struct.unpack_from('<I', buf, 12)
        header_size = min(max(header_size, _BASE_SIZE), len(buf))
        hdr = cls._unpack_header(buf, header_size)

        vtf = cls()
        vtf.version = hdr['version']
        vtf.width, vtf.height, vtf.depth = hdr['width'], hdr['height'], hdr['depth']
        vtf.flags, vtf.frames, vtf.start_frame = hdr['flags'], hdr['frames'], hdr['start_frame']
        vtf.reflectivity, vtf.bump_scale = hdr['reflectivity'], hdr['bump_scale']
        vtf.image_format = hdr['image_format']
        vtf.low_res_image_format = hdr['low_res_image_format']
        vtf.low_res_image_width = hdr['low_res_image_width']
        vtf.low_res_image_height = hdr['low_res_image_height']
        mip_count = hdr['mip_count']

        vtf.faces = 1
        if vtf.flags & VTFFlags.ENVMAP:
            vtf.faces = 7 if (vtf.start_frame != 0xFFFF and vtf.version < (7, 5)) else 6

        if header_only:
            return vtf

        thumb_off = img_off = None
        if hdr['resource_count']:
            pos = hdr['resource_dir_offset']
            for _ in range(hdr['resource_count']):
                rtype, rdata = struct.unpack_from('<II', buf, pos)
                pos += 8
                has_no_chunk = bool((rtype >> 24) & 0x02)
                if rtype == VTFResourceType.LOW_RES_IMAGE:
                    thumb_off = rdata
                elif rtype == VTFResourceType.IMAGE:
                    img_off = rdata
                elif has_no_chunk:
                    vtf.resources[rtype] = struct.pack('<I', rdata)
                else:
                    size, = struct.unpack_from('<I', buf, rdata)
                    vtf.resources[rtype] = buf[rdata + 4: rdata + 4 + size]
        else:
            pos = header_size
            if vtf.low_res_image_format != ImageFormat.NONE:
                thumb_off = pos
                pos += compute_image_size(vtf.low_res_image_width, vtf.low_res_image_height,
                                           1, vtf.low_res_image_format)
            img_off = pos

        if thumb_off is not None:
            size = compute_image_size(vtf.low_res_image_width, vtf.low_res_image_height,
                                       1, vtf.low_res_image_format)
            vtf.thumbnail_data = buf[thumb_off:thumb_off + size]

        vtf.image_mips = [None] * mip_count
        if img_off is not None and vtf.image_format != ImageFormat.NONE:
            pos = img_off
            for mip in range(mip_count - 1, -1, -1):
                w, h, d = mipmap_dimensions(vtf.width, vtf.height, vtf.depth, mip)
                slice_size = compute_image_size(w, h, 1, vtf.image_format)
                mip_data = []
                for _f in range(vtf.frames):
                    frame_data = []
                    for _c in range(vtf.faces):
                        face_data = []
                        for _s in range(d):
                            face_data.append(buf[pos:pos + slice_size])
                            pos += slice_size
                        frame_data.append(face_data)
                    mip_data.append(frame_data)
                vtf.image_mips[mip] = mip_data
        return vtf

    # -------------------------------------------------------------- saving --
    def save(self, dest=None):
        """Serialize to bytes; optionally also write to a file path."""
        data = self._build()
        if dest is not None:
            with open(dest, 'wb') as f:
                f.write(data)
        return data

    def _pack_image_data(self):
        out = bytearray()
        for mip in range(self.mip_count - 1, -1, -1):
            for frame_data in self.image_mips[mip]:
                for face_data in frame_data:
                    for chunk in face_data:
                        out += chunk
        return bytes(out)

    def _build(self):
        version = self.version
        mip_count = max(self.mip_count, 1)
        has_thumb = self.low_res_image_format != ImageFormat.NONE and bool(self.thumbnail_data)
        use_resources = version >= (7, 3)

        base = struct.pack(
            _BASE_FMT, b'VTF\x00', version[0], version[1], 0,
            self.width, self.height, self.flags, self.frames, self.start_frame,
            *self.reflectivity, self.bump_scale, int(self.image_format), mip_count,
            int(self.low_res_image_format if has_thumb else ImageFormat.NONE),
            self.low_res_image_width if has_thumb else 0,
            self.low_res_image_height if has_thumb else 0,
        )
        buf = bytearray(base)
        if version >= (7, 2):
            buf += struct.pack('<H', self.depth)

        resource_list = []
        if use_resources:
            if has_thumb:
                resource_list.append((VTFResourceType.LOW_RES_IMAGE, None))
            resource_list.append((VTFResourceType.IMAGE, None))
            resource_list.extend(self.resources.items())
            buf += b'\x00\x00\x00' + struct.pack('<I', len(resource_list))

        header_size = _align16(len(buf))
        buf += b'\x00' * (header_size - len(buf))

        image_bytes = self._pack_image_data()
        thumb_bytes = self.thumbnail_data if has_thumb else b''

        resource_entries = bytearray()
        body = bytearray()
        if use_resources:
            header_size += 8 * len(resource_list)
            cursor = header_size
            for rtype, rdata in resource_list:
                has_no_chunk = bool((rtype >> 24) & 0x02)
                if rtype == VTFResourceType.LOW_RES_IMAGE:
                    resource_entries += struct.pack('<II', rtype, cursor)
                    body += thumb_bytes
                    cursor += len(thumb_bytes)
                elif rtype == VTFResourceType.IMAGE:
                    resource_entries += struct.pack('<II', rtype, cursor)
                    body += image_bytes
                    cursor += len(image_bytes)
                elif has_no_chunk:
                    val, = struct.unpack('<I', bytes(rdata[:4]).ljust(4, b'\x00'))
                    resource_entries += struct.pack('<II', rtype, val)
                else:
                    resource_entries += struct.pack('<II', rtype, cursor)
                    body += struct.pack('<I', len(rdata)) + rdata
                    cursor += 4 + len(rdata)
        else:
            body += thumb_bytes
            body += image_bytes

        struct.pack_into('<I', buf, 12, header_size)
        return bytes(buf) + bytes(resource_entries) + bytes(body)

    # -------------------------------------------------------- pixel access --
    def get_data(self, frame=0, face=0, slice_=0, mip=0):
        """Raw bytes for one image, in the texture's native pixel format."""
        return self.image_mips[mip][frame][face][slice_]

    def set_data(self, data, frame=0, face=0, slice_=0, mip=0):
        self.image_mips[mip][frame][face][slice_] = bytes(data)

    def get_rgba(self, frame=0, face=0, slice_=0, mip=0):
        """Decoded RGBA8888 bytes for one image."""
        w, h, _ = mipmap_dimensions(self.width, self.height, self.depth, mip)
        return _convert.to_rgba8888(self.get_data(frame, face, slice_, mip), w, h, self.image_format)

    def set_rgba(self, rgba, frame=0, face=0, slice_=0, mip=0):
        """Encode RGBA8888 bytes into the texture's native format and store them."""
        w, h, _ = mipmap_dimensions(self.width, self.height, self.depth, mip)
        self.set_data(_convert.from_rgba8888(rgba, w, h, self.image_format), frame, face, slice_, mip)

    def get_thumbnail_rgba(self):
        if not self.thumbnail_data:
            return None
        return _convert.to_rgba8888(self.thumbnail_data, self.low_res_image_width,
                                     self.low_res_image_height, self.low_res_image_format)

    def get_resource(self, resource_type):
        return self.resources.get(resource_type)

    def set_resource(self, resource_type, data):
        self.resources[resource_type] = bytes(data)

    # ------------------------------------------------------------- helpers --
    def generate_mipmaps(self):
        """Regenerate all mip levels from level 0 using a box filter."""
        base = [[[self.get_rgba(f, c, s, 0) for s in range(self.depth)]
                 for c in range(self.faces)] for f in range(self.frames)]
        rebuilt = VTFFile.create(self.width, self.height, base, self.frames, self.faces,
                                  self.depth, self.image_format, mipmaps=True,
                                  thumbnail=False, version=self.version)
        self.image_mips = rebuilt.image_mips

    def generate_thumbnail(self):
        """Regenerate the low-res (DXT1) thumbnail from level 0, face 0."""
        tw, th = self.width, self.height
        while tw > 16 or th > 16:
            tw, th = max(tw // 2, 1), max(th // 2, 1)
        rgba = _resize_rgba(self.get_rgba(0, 0, 0, 0), self.width, self.height, tw, th)
        self.low_res_image_format = ImageFormat.DXT1
        self.low_res_image_width, self.low_res_image_height = tw, th
        self.thumbnail_data = _convert.from_rgba8888(rgba, tw, th, ImageFormat.DXT1)

    # ------------------------------------------------------------- creation --
    @classmethod
    def create(cls, width, height, rgba, frames=1, faces=1, depth=1,
               image_format=ImageFormat.DXT5, mipmaps=True, thumbnail=True,
               version=(7, 4)):
        """Build a new VTF from RGBA8888 source data.

        `rgba` may be a single ``bytes`` object (for frames=faces=depth=1)
        or nested as ``rgba[frame][face][slice] -> bytes``.
        """
        vtf = cls()
        vtf.version = version
        vtf.width, vtf.height, vtf.depth = width, height, depth
        vtf.frames, vtf.faces = frames, faces
        vtf.image_format = ImageFormat(image_format)
        if faces >= 6:
            vtf.flags |= VTFFlags.ENVMAP

        if isinstance(rgba, (bytes, bytearray)):
            rgba = [[[bytes(rgba)]]]

        mip_count = compute_mipmap_count(width, height, depth) if mipmaps else 1
        vtf.image_mips = [None] * mip_count

        cur = [[[rgba[f][c][s] for s in range(depth)] for c in range(faces)] for f in range(frames)]
        cw, ch = width, height
        for level in range(mip_count):
            vtf.image_mips[level] = [
                [[_convert.from_rgba8888(cur[f][c][s], cw, ch, vtf.image_format) for s in range(depth)]
                 for c in range(faces)] for f in range(frames)
            ]
            if level + 1 < mip_count:
                nxt = [[[None] * depth for _ in range(faces)] for _ in range(frames)]
                nw = nh = None
                for f in range(frames):
                    for c in range(faces):
                        for s in range(depth):
                            nxt[f][c][s], nw, nh = _box_downsample_rgba(cur[f][c][s], cw, ch)
                cur, cw, ch = nxt, nw, nh

        if thumbnail:
            vtf.generate_thumbnail_from(rgba[0][0][0], width, height)
        return vtf

    def generate_thumbnail_from(self, rgba, width, height):
        tw, th = width, height
        while tw > 16 or th > 16:
            tw, th = max(tw // 2, 1), max(th // 2, 1)
        thumb_rgba = _resize_rgba(rgba, width, height, tw, th)
        self.low_res_image_format = ImageFormat.DXT1
        self.low_res_image_width, self.low_res_image_height = tw, th
        self.thumbnail_data = _convert.from_rgba8888(thumb_rgba, tw, th, ImageFormat.DXT1)

    # ---------------------------------------------------- static VTFLib API --
    ComputeImageSize = staticmethod(compute_image_size)
    ComputeMipmapCount = staticmethod(compute_mipmap_count)
    ComputeMipmapDimensions = staticmethod(mipmap_dimensions)
    ComputeMipmapSize = staticmethod(compute_mipmap_size)

    def __repr__(self):
        return (f"<VTFFile {self.width}x{self.height}x{self.depth} "
                f"{self.image_format.name} frames={self.frames} faces={self.faces} "
                f"mips={self.mip_count}>")
