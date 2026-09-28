import pytest

from raylite.mesh import MeshError, parse_obj
from raylite.shapes import Material
from raylite.vec3 import Vec3

MAT = Material(color=Vec3(1, 0, 0))

SINGLE_TRIANGLE = """
v -1 -1 -5
v 1 -1 -5
v 0 1 -5
f 1 2 3
"""

QUAD = """
v 0 0 0
v 1 0 0
v 1 1 0
v 0 1 0
f 1 2 3 4
"""


def test_parse_single_triangle():
    triangles = parse_obj(SINGLE_TRIANGLE, MAT)
    assert len(triangles) == 1
    tri = triangles[0]
    assert tri.v0 == Vec3(-1, -1, -5)
    assert tri.v1 == Vec3(1, -1, -5)
    assert tri.v2 == Vec3(0, 1, -5)
    assert tri.material is MAT


def test_fan_triangulates_quad():
    triangles = parse_obj(QUAD, MAT)
    assert len(triangles) == 2
    assert triangles[0].v0 == Vec3(0, 0, 0)
    assert triangles[1].v0 == Vec3(0, 0, 0)


def test_ignores_comments_and_blank_lines():
    text = "# a comment\n\nv -1 -1 -5\nv 1 -1 -5  # trailing comment\nv 0 1 -5\nf 1 2 3\n"
    triangles = parse_obj(text, MAT)
    assert len(triangles) == 1


def test_ignores_unsupported_keywords():
    text = SINGLE_TRIANGLE + "vn 0 0 1\nvt 0.5 0.5\no MyObject\n"
    triangles = parse_obj(text, MAT)
    assert len(triangles) == 1


def test_face_with_vertex_texture_normal_indices():
    text = "v -1 -1 -5\nv 1 -1 -5\nv 0 1 -5\nf 1/1/1 2/2/1 3/3/1\n"
    triangles = parse_obj(text, MAT)
    assert len(triangles) == 1


def test_negative_relative_face_indices():
    text = "v -1 -1 -5\nv 1 -1 -5\nv 0 1 -5\nf -3 -2 -1\n"
    triangles = parse_obj(text, MAT)
    assert len(triangles) == 1
    assert triangles[0].v0 == Vec3(-1, -1, -5)


def test_face_index_out_of_range_raises():
    text = "v -1 -1 -5\nv 1 -1 -5\nv 0 1 -5\nf 1 2 4\n"
    with pytest.raises(MeshError, match="out of range"):
        parse_obj(text, MAT)


def test_invalid_vertex_coordinate_raises():
    with pytest.raises(MeshError, match="invalid vertex coordinate"):
        parse_obj("v x -1 -5\n", MAT)


def test_face_with_too_few_vertices_raises():
    with pytest.raises(MeshError, match="at least 3"):
        parse_obj("v 0 0 0\nv 1 0 0\nf 1 2\n", MAT)


def test_empty_text_yields_no_triangles():
    assert parse_obj("", MAT) == []
