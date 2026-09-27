import random

from raylite.render import closest_hit, render, shade, trace_ray
from raylite.ray import Ray
from raylite.scene import Camera, Light, Scene
from raylite.shapes import Material, Sphere
from raylite.vec3 import Vec3


def make_scene(reflectivity=0.0, ambient=0.1):
    material = Material(color=Vec3(1, 0, 0), diffuse=0.8, specular=0.2, reflectivity=reflectivity)
    sphere = Sphere(center=Vec3(0, 0, -5), radius=1, material=material)
    camera = Camera(origin=Vec3(0, 0, 0), look_at=Vec3(0, 0, -1), up=Vec3(0, 1, 0))
    light = Light(position=Vec3(5, 5, 0), color=Vec3(1, 1, 1), intensity=1.0)
    return Scene(camera=camera, shapes=[sphere], lights=[light], background=Vec3(0, 0, 0), ambient=ambient)


def test_closest_hit_returns_nearest_shape():
    scene = make_scene()
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(0, 0, -1))
    hit = closest_hit(scene, ray)
    assert hit is not None
    assert hit.t == 4


def test_closest_hit_none_when_no_shapes_hit():
    scene = make_scene()
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(1, 0, 0))
    assert closest_hit(scene, ray) is None


def test_trace_ray_returns_background_on_miss():
    scene = make_scene()
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(1, 0, 0))
    color = trace_ray(scene, ray)
    assert color == scene.background


def test_shade_includes_ambient_even_in_full_shadow():
    scene = make_scene(ambient=0.2)
    # Put a second sphere directly between the light and the hit point to force shadow.
    blocker = Sphere(center=Vec3(2.5, 2.5, -2.5), radius=5, material=scene.shapes[0].material)
    scene.shapes.append(blocker)
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(0, 0, -1))
    hit = closest_hit(scene, ray)
    color = shade(scene, hit, ray.direction)
    assert color.x > 0  # ambient contribution survives full shadow
    assert color.x < scene.shapes[0].material.color.x  # but shadow means no direct light added


def test_shade_lit_point_brighter_than_shadowed_point():
    scene = make_scene()
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(0, 0, -1))
    hit = closest_hit(scene, ray)
    lit_color = shade(scene, hit, ray.direction)

    scene_no_light = make_scene()
    scene_no_light.lights = []
    unlit_color = shade(scene_no_light, hit, ray.direction)

    assert lit_color.x > unlit_color.x


def test_reflective_material_blends_reflected_color():
    scene = make_scene(reflectivity=0.5)
    scene.background = Vec3(0, 0, 1)  # distinct color to detect in the reflection
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(0, 0, -1))
    hit = closest_hit(scene, ray)
    color = shade(scene, hit, ray.direction)
    # Reflected ray from the sphere's front-facing point bounces straight back,
    # so it should pick up some blue from the background.
    assert color.z > 0


def test_render_produces_correct_grid_dimensions():
    scene = make_scene()
    pixels = render(scene, width=8, height=6, samples_per_pixel=1)
    assert len(pixels) == 6
    assert all(len(row) == 8 for row in pixels)


def test_render_is_deterministic_with_seeded_rng_and_multisample():
    scene = make_scene()
    pixels_a = render(scene, width=4, height=4, samples_per_pixel=4, rng=random.Random(42))
    pixels_b = render(scene, width=4, height=4, samples_per_pixel=4, rng=random.Random(42))
    assert pixels_a == pixels_b


def test_render_center_pixel_hits_sphere_not_background():
    scene = make_scene()
    pixels = render(scene, width=5, height=5, samples_per_pixel=1)
    center = pixels[2][2]
    assert center != scene.background
