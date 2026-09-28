"""Minimal Wavefront .obj loader: parses vertices and faces into Triangles.

Only the subset needed for a small ray tracer is supported: `v x y z`
vertex lines and `f` face lines (triangles or convex polygons, fan-
triangulated). Texture/normal indices in a face line (`v/vt/vn`) are
accepted but ignored — shading uses each triangle's own geometric
normal, not interpolated vertex normals. Negative (relative) vertex
indices are supported since some exporters emit them.
"""

from __future__ import annotations

from typing import List

from raylite.shapes import Material, Triangle
from raylite.vec3 import Vec3


class MeshError(ValueError):
    pass


def _parse_face_index(token: str, vertex_count: int) -> int:
    index_str = token.split("/")[0]
    try:
        index = int(index_str)
    except ValueError as exc:
        raise MeshError(f"invalid face vertex index: {token!r}") from exc
    if index < 0:
        index = vertex_count + index + 1
    if index < 1 or index > vertex_count:
        raise MeshError(f"face vertex index out of range: {token!r}")
    return index - 1


def parse_obj(text: str, material: Material) -> List[Triangle]:
    vertices: List[Vec3] = []
    triangles: List[Triangle] = []

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        keyword = parts[0]

        if keyword == "v":
            if len(parts) < 4:
                raise MeshError(f"line {lineno}: 'v' needs 3 coordinates")
            try:
                x, y, z = (float(parts[1]), float(parts[2]), float(parts[3]))
            except ValueError as exc:
                raise MeshError(f"line {lineno}: invalid vertex coordinate") from exc
            vertices.append(Vec3(x, y, z))
        elif keyword == "f":
            if len(parts) < 4:
                raise MeshError(f"line {lineno}: 'f' needs at least 3 vertices")
            indices = [_parse_face_index(tok, len(vertices)) for tok in parts[1:]]
            # Fan-triangulate any polygon with more than 3 vertices.
            for i in range(1, len(indices) - 1):
                triangles.append(
                    Triangle(
                        vertices[indices[0]],
                        vertices[indices[i]],
                        vertices[indices[i + 1]],
                        material,
                    )
                )
        # Other keywords (vt, vn, o, g, s, mtllib, usemtl, ...) are ignored.

    return triangles


def load_obj(path: str, material: Material) -> List[Triangle]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return parse_obj(text, material)
