"""Scene primitives: spheres and planes, each with a material."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from raylite.ray import Ray
from raylite.vec3 import Vec3


@dataclass
class Material:
    color: Vec3
    diffuse: float = 0.8
    specular: float = 0.2
    shininess: float = 32.0
    reflectivity: float = 0.0


@dataclass
class Hit:
    t: float
    point: Vec3
    normal: Vec3
    material: Material


class Sphere:
    def __init__(self, center: Vec3, radius: float, material: Material):
        self.center = center
        self.radius = radius
        self.material = material

    def hit(self, ray: Ray, t_min: float, t_max: float) -> Optional[Hit]:
        oc = ray.origin - self.center
        a = ray.direction.dot(ray.direction)
        b = 2.0 * oc.dot(ray.direction)
        c = oc.dot(oc) - self.radius * self.radius
        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return None
        sqrt_d = math.sqrt(discriminant)
        for t in ((-b - sqrt_d) / (2 * a), (-b + sqrt_d) / (2 * a)):
            if t_min < t < t_max:
                point = ray.at(t)
                normal = (point - self.center).normalize()
                return Hit(t=t, point=point, normal=normal, material=self.material)
        return None


class Plane:
    """An infinite plane defined by a point on it and a unit normal."""

    def __init__(self, point: Vec3, normal: Vec3, material: Material):
        self.point = point
        self.normal = normal.normalize()
        self.material = material

    def hit(self, ray: Ray, t_min: float, t_max: float) -> Optional[Hit]:
        denom = ray.direction.dot(self.normal)
        if abs(denom) < 1e-9:
            return None
        t = (self.point - ray.origin).dot(self.normal) / denom
        if t_min < t < t_max:
            point = ray.at(t)
            normal = self.normal if denom < 0 else -self.normal
            return Hit(t=t, point=point, normal=normal, material=self.material)
        return None
