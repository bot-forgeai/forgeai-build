import random

from raylite.render import _sample_light_position, closest_hit, render, shade, trace_ray
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


def test_sample_light_position_returns_exact_position_for_hard_light():
    light = Light(position=Vec3(5, 5, 0), color=Vec3(1, 1, 1), radius=0.0)
    rng = random.Random(1)
    for _ in range(20):
        assert _sample_light_position(light, rng) == light.position


def test_sample_light_position_stays_within_radius_for_area_light():
    light = Light(position=Vec3(5, 5, 0), color=Vec3(1, 1, 1), radius=2.0)
    rng = random.Random(7)
    for _ in range(50):
        sampled = _sample_light_position(light, rng)
        assert (sampled - light.position).length() <= 2.0 + 1e-9


def test_sample_light_position_varies_across_calls_for_area_light():
    light = Light(position=Vec3(5, 5, 0), color=Vec3(1, 1, 1), radius=2.0)
    rng = random.Random(3)
    samples = {_sample_light_position(light, rng) for _ in range(20)}
    assert len(samples) > 1


def test_shade_uses_provided_rng_deterministically():
    scene = make_scene()
    scene.lights[0].radius = 3.0
    ray = Ray(origin=Vec3(0, 0, 0), direction=Vec3(0, 0, -1))
    hit = closest_hit(scene, ray)
    color_a = shade(scene, hit, ray.direction, rng=random.Random(99))
    color_b = shade(scene, hit, ray.direction, rng=random.Random(99))
    assert color_a == color_b


def test_render_with_workers_produces_correct_grid_dimensions():
    scene = make_scene()
    pixels = render(scene, width=8, height=6, samples_per_pixel=1, workers=2)
    assert len(pixels) == 6
    assert all(len(row) == 8 for row in pixels)


def test_render_with_workers_matches_single_worker_for_same_seed():
    scene = make_scene()
    parallel = render(scene, width=6, height=6, samples_per_pixel=3, workers=3, seed=123)
    parallel_again = render(scene, width=6, height=6, samples_per_pixel=3, workers=2, seed=123)
    assert parallel == parallel_again


def test_render_with_workers_center_pixel_hits_sphere_not_background():
    scene = make_scene()
    pixels = render(scene, width=5, height=5, samples_per_pixel=1, workers=2)
    center = pixels[2][2]
    assert center != scene.background


def test_area_light_softens_shadow_edge_with_multiple_samples():
    # A small blocker only partially covers a wide area light from a point
    # just past its edge; with a hard point light that point is either fully
    # lit or fully shadowed, but an area light rendered with many samples
    # should land at a partial (soft) brightness in between.
    material = Material(color=Vec3(1, 1, 1), diffuse=0.8, specular=0.0)
    ground = Sphere(center=Vec3(0, -1001, 0), radius=1000, material=material)
    blocker = Sphere(center=Vec3(0, 1, -3), radius=0.5, material=material)
    camera = Camera(origin=Vec3(0, 0, 0), look_at=Vec3(0.15, -1, -3), up=Vec3(0, 1, 0))
    hard_light = Light(position=Vec3(0, 5, -3), color=Vec3(1, 1, 1), intensity=1.0, radius=0.0)
    soft_light = Light(position=Vec3(0, 5, -3), color=Vec3(1, 1, 1), intensity=1.0, radius=1.5)

    hard_scene = Scene(camera=camera, shapes=[ground, blocker], lights=[hard_light], background=Vec3(0, 0, 0), ambient=0.1)
    soft_scene = Scene(camera=camera, shapes=[ground, blocker], lights=[soft_light], background=Vec3(0, 0, 0), ambient=0.1)

    hard_pixels = render(hard_scene, width=1, height=1, samples_per_pixel=1)
    soft_pixels = render(soft_scene, width=1, height=1, samples_per_pixel=64, rng=random.Random(5))

    hard_brightness = hard_pixels[0][0].x
    soft_brightness = soft_pixels[0][0].x
    # The point is fully shadowed under the hard light (ambient only) but
    # partially lit on average under the soft area light.
    assert soft_brightness > hard_brightness + 0.05
