from raylite.ray import Ray
from raylite.shapes import Material, Plane, Sphere
from raylite.vec3 import Vec3

MAT = Material(color=Vec3(1, 0, 0))


def test_sphere_hit_straight_on():
    sphere = Sphere(center=Vec3(0, 0, -5), radius=1, material=MAT)
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(0, 0, -1))
    hit = sphere.hit(ray, 1e-4, float("inf"))
    assert hit is not None
    assert hit.t == 4
    assert hit.point == Vec3(0, 0, -4)
    assert hit.normal == Vec3(0, 0, 1)


def test_sphere_miss():
    sphere = Sphere(center=Vec3(5, 5, -5), radius=1, material=MAT)
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(0, 0, -1))
    assert sphere.hit(ray, 1e-4, float("inf")) is None


def test_sphere_respects_t_max():
    sphere = Sphere(center=Vec3(0, 0, -5), radius=1, material=MAT)
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(0, 0, -1))
    assert sphere.hit(ray, 1e-4, 3.0) is None


def test_sphere_hit_from_inside_uses_far_root():
    sphere = Sphere(center=Vec3(0, 0, 0), radius=2, material=MAT)
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(0, 0, -1))
    hit = sphere.hit(ray, 1e-4, float("inf"))
    assert hit is not None
    assert hit.t == 2


def test_plane_hit():
    plane = Plane(point=Vec3(0, 0, 0), normal=Vec3(0, 1, 0), material=MAT)
    ray = Ray(origin=Vec3(0, 5, 0), direction=Vec3(0, -1, 0))
    hit = plane.hit(ray, 1e-4, float("inf"))
    assert hit is not None
    assert hit.t == 5
    assert hit.point == Vec3(0, 0, 0)
    assert hit.normal == Vec3(0, 1, 0)


def test_plane_parallel_ray_misses():
    plane = Plane(point=Vec3(0, 0, 0), normal=Vec3(0, 1, 0), material=MAT)
    ray = Ray(origin=Vec3(0, 5, 0), direction=Vec3(1, 0, 0))
    assert plane.hit(ray, 1e-4, float("inf")) is None


def test_plane_normal_faces_ray():
    plane = Plane(point=Vec3(0, 0, 0), normal=Vec3(0, 1, 0), material=MAT)
    ray_from_below = Ray(origin=Vec3(0, -5, 0), direction=Vec3(0, 1, 0))
    hit = plane.hit(ray_from_below, 1e-4, float("inf"))
    assert hit is not None
    assert hit.normal == Vec3(0, -1, 0)
