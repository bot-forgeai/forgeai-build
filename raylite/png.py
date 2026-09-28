"""Writes a rendered pixel grid out as an 8-bit RGB PNG image.

A minimal encoder (signature + IHDR + one zlib-compressed IDAT of
unfiltered scanlines + IEND) so a render can be viewed directly by any
image viewer, without needing an external pnmtopng/convert step the
way the existing PPM writer does.
"""

from __future__ import annotations

import struct
import zlib
from typing import List

from raylite.vec3 import Vec3

_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def write_png(path: str, pixels: List[List[Vec3]]) -> None:
    height = len(pixels)
    width = len(pixels[0]) if height else 0

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    raw = bytearray()
    for row in pixels:
        raw.append(0)  # filter type: none
        for color in row:
            raw.extend(
                max(0, min(255, int(round(c * 255)))) for c in (color.x, color.y, color.z)
            )
    idat = zlib.compress(bytes(raw), 9)

    with open(path, "wb") as f:
        f.write(_SIGNATURE)
        f.write(_chunk(b"IHDR", ihdr))
        f.write(_chunk(b"IDAT", idat))
        f.write(_chunk(b"IEND", b""))
