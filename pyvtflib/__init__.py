"""
pyvtflib - a pure-Python, dependency-free reimplementation of VTFLib.

Supports reading/writing Valve's VTF (texture) and VMT (material) file
formats on any platform Python runs on (Windows, Linux, macOS, ...),
without any native/compiled dependencies.

Quick start
-----------
    from pyvtflib import VTFFile, ImageFormat

    tex = VTFFile.load("example.vtf")
    rgba = tex.get_rgba()                 # bytes, RGBA8888, level 0
    tex.save("copy.vtf")

    new = VTFFile.create(256, 256, rgba_bytes, image_format=ImageFormat.DXT5)
    new.save("new.vtf")

    from pyvtflib import VMTFile
    mat = VMTFile.load("example.vmt")
    print(mat.root["$basetexture"])
    mat.save("copy.vmt")
"""
from .formats import ImageFormat
from .vtf import VTFFile, VTFFlags, VTFResourceType
from .vmt import (
    VMTFile,
    VMTNode,
    VMTGroupNode,
    VMTStringNode,
    VMTIntegerNode,
    VMTFloatNode,
)

__all__ = [
    "ImageFormat",
    "VTFFile",
    "VTFFlags",
    "VTFResourceType",
    "VMTFile",
    "VMTNode",
    "VMTGroupNode",
    "VMTStringNode",
    "VMTIntegerNode",
    "VMTFloatNode",
]

__version__ = "1.0.0"
