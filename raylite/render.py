"""The renderer: ray/scene intersection, Phong-ish shading, shadows, reflection."""

from __future__ import annotations

import random
from typing import List, Optional

from raylite.camera import CameraRays
from raylite.ray import Ray
from raylite.scene import Scene
from raylite.shapes import Hit
from raylite.vec3 import Vec3

SHADOW_BIAS = 1e-4
MAX_REFLECT_DEPTH = 3


def closest_hit(scene: Scene, ray: Ray, t_min: float = 1e-4, t_max: float = float("inf")) -> Optional[Hit]:
    nearest: Optional[Hit] = None
    closest_t = t_max
    for shape in scene.shapes:
        hit = shape.hit(ray, t_min, closest_t)
        if hit is not None:
            nearest = hit
            closest_t = hit.t
    return nearest


def _in_shadow(scene: Scene, point: Vec3, light_position: Vec3) -> bool:
    to_light = light_position - point
    distance = to_light.length()
    if distance == 0:
        return False
    direction = to_light / distance
    shadow_ray = Ray(origin=point + direction * SHADOW_BIAS, direction=direction)
    return closest_hit(scene, shadow_ray, t_min=1e-4, t_max=distance) is not None


def shade(scene: Scene, hit: Hit, view_direction: Vec3, depth: int = 0) -> Vec3:
    material = hit.material
    color = material.color * scene.ambient

    for light in scene.lights:
        if _in_shadow(scene, hit.point, light.position):
            continue
        to_light = (light.position - hit.point).normalize()
        diffuse_strength = max(0.0, hit.normal.dot(to_light))
        color = color + material.color.multiply(light.color) * (
            material.diffuse * diffuse_strength * light.intensity
        )

        if diffuse_strength > 0:
            reflect_dir = (-to_light).reflect(hit.normal)
            spec_strength = max(0.0, (-view_direction).dot(reflect_dir)) ** material.shininess
            color = color + light.color * (material.specular * spec_strength * light.intensity)

    if material.reflectivity > 0 and depth < MAX_REFLECT_DEPTH:
        reflect_dir = view_direction.reflect(hit.normal)
        reflect_ray = Ray(origin=hit.point + hit.normal * SHADOW_BIAS, direction=reflect_dir)
        reflected_color = trace_ray(scene, reflect_ray, depth + 1)
        color = color * (1 - material.reflectivity) + reflected_color * material.reflectivity

    return color


def trace_ray(scene: Scene, ray: Ray, depth: int = 0) -> Vec3:
    hit = closest_hit(scene, ray)
    if hit is None:
        return scene.background
    return shade(scene, hit, ray.direction, depth)


def render(scene: Scene, width: int, height: int, samples_per_pixel: int = 1, rng: Optional[random.Random] = None) -> List[List[Vec3]]:
    """Renders the scene to a height x width grid of Vec3 colors (each channel in [0, 1])."""
    rng = rng or random.Random()
    cam = CameraRays(scene.camera, width, height)
    pixels: List[List[Vec3]] = []
    for y in range(height):
        row = []
        for x in range(width):
            accum = Vec3(0, 0, 0)
            for _ in range(samples_per_pixel):
                if samples_per_pixel == 1:
                    jitter_x, jitter_y = 0.5, 0.5
                else:
                    jitter_x, jitter_y = rng.random(), rng.random()
                ray = cam.ray_for_pixel(x + jitter_x, y + jitter_y)
                accum = accum + trace_ray(scene, ray)
            row.append((accum / samples_per_pixel).clamp01())
        pixels.append(row)
    return pixels
