"""Quick self-test: create/save/load round-trips for VTF and VMT.

Run with:  python -m pyvtflib._selftest
"""
import random

from .formats import ImageFormat
from .vtf import VTFFile
from .vmt import VMTFile


def _checker_rgba(w, h):
    out = bytearray(w * h * 4)
    for y in range(h):
        for x in range(w):
            c = 255 if (x // 4 + y // 4) % 2 == 0 else 40
            o = (y * w + x) * 4
            out[o:o + 4] = bytes((c, 128, 255 - c, 255 if x > w // 2 else 128))
    return bytes(out)


def test_vtf_roundtrip(fmt, w=32, h=32):
    rgba = _checker_rgba(w, h)
    tex = VTFFile.create(w, h, rgba, image_format=fmt, mipmaps=True, thumbnail=True)
    data = tex.save()
    loaded = VTFFile.load(data)
    assert loaded.width == w and loaded.height == h
    assert loaded.image_format == fmt
    assert loaded.mip_count == tex.mip_count
    out_rgba = loaded.get_rgba()
    assert len(out_rgba) == len(rgba)
    print(f"  {fmt.name:10s} OK  ({len(data)} bytes, {loaded.mip_count} mips, "
          f"thumb={loaded.low_res_image_width}x{loaded.low_res_image_height})")


def test_vmt_roundtrip():
    src = '''
    // a comment
    "LightmappedGeneric"
    {
        "$basetexture" "brick/brick01"
        "$bumpmap"     "brick/brick01_normal"
        "$surfaceprop" "brick"
        "$envmapTint"  .1 .1 .1
        "Proxies"
        {
            "AnimatedTexture"
            {
                "animatedtexturevar" "$basetexture"
                "animatedtextureframerate" "4"
            }
        }
    }
    '''
    mat = VMTFile.loads(src)
    assert mat.root.name == "LightmappedGeneric"
    assert mat.root["$basetexture"] == "brick/brick01"
    assert mat.root["$surfaceprop"] == "brick"
    proxies = mat.root.get("Proxies")
    assert proxies is not None and len(proxies.nodes) == 1
    text = mat.save()
    mat2 = VMTFile.loads(text)
    assert mat2.root["$basetexture"] == "brick/brick01"
    print("  VMT round-trip OK")


def main():
    random.seed(0)
    print("VTF round-trips:")
    for fmt in (ImageFormat.RGBA8888, ImageFormat.BGRA8888, ImageFormat.RGB888,
                ImageFormat.I8, ImageFormat.DXT1, ImageFormat.DXT3, ImageFormat.DXT5):
        test_vtf_roundtrip(fmt)
    print("VMT round-trip:")
    test_vmt_roundtrip()
    print("All good.")


if __name__ == "__main__":
    main()
