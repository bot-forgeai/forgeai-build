import math

from raylite.vec3 import Vec3


def test_add_sub_neg():
    a = Vec3(1, 2, 3)
    b = Vec3(4, 5, 6)
    assert a + b == Vec3(5, 7, 9)
    assert b - a == Vec3(3, 3, 3)
    assert -a == Vec3(-1, -2, -3)


def test_scalar_mul_div():
    a = Vec3(1, 2, 3)
    assert a * 2 == Vec3(2, 4, 6)
    assert 2 * a == Vec3(2, 4, 6)
    assert a / 2 == Vec3(0.5, 1, 1.5)


def test_multiply_componentwise():
    a = Vec3(1, 2, 3)
    b = Vec3(2, 2, 2)
    assert a.multiply(b) == Vec3(2, 4, 6)


def test_dot_and_cross():
    a = Vec3(1, 0, 0)
    b = Vec3(0, 1, 0)
    assert a.dot(b) == 0
    assert a.cross(b) == Vec3(0, 0, 1)


def test_length_and_normalize():
    a = Vec3(3, 4, 0)
    assert a.length() == 5
    n = a.normalize()
    assert math.isclose(n.length(), 1.0)


def test_normalize_zero_vector_returns_self():
    z = Vec3(0, 0, 0)
    assert z.normalize() == z


def test_reflect():
    incoming = Vec3(1, -1, 0).normalize()
    normal = Vec3(0, 1, 0)
    reflected = incoming.reflect(normal)
    assert math.isclose(reflected.x, incoming.x)
    assert math.isclose(reflected.y, -incoming.y)


def test_clamp01():
    a = Vec3(-0.5, 0.5, 1.5)
    assert a.clamp01() == Vec3(0.0, 0.5, 1.0)
