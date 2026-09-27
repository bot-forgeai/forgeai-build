"""Writes a rendered pixel grid out as a binary PPM (P6) image."""

from __future__ import annotations

from typing import List

from raylite.vec3 import Vec3


def write_ppm(path: str, pixels: List[List[Vec3]]) -> None:
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    with open(path, "wb") as f:
        f.write(f"P6\n{width} {height}\n255\n".encode("ascii"))
        for row in pixels:
            for color in row:
                f.write(bytes(int(round(c * 255)) for c in (color.x, color.y, color.z)))
