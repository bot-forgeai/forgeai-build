"""Converts pixel coordinates into camera rays for a given image size."""

from __future__ import annotations

import math

from raylite.ray import Ray
from raylite.scene import Camera
from raylite.vec3 import Vec3


class CameraRays:
    def __init__(self, camera: Camera, image_width: int, image_height: int):
        self.origin = camera.origin
        forward = (camera.look_at - camera.origin).normalize()
        right = forward.cross(camera.up).normalize()
        true_up = right.cross(forward).normalize()

        aspect_ratio = image_width / image_height
        theta = math.radians(camera.fov_degrees)
        half_height = math.tan(theta / 2)
        half_width = half_height * aspect_ratio

        self.forward = forward
        self.right = right
        self.up = true_up
        self.half_width = half_width
        self.half_height = half_height
        self.image_width = image_width
        self.image_height = image_height

    def ray_for_pixel(self, px: float, py: float) -> Ray:
        """px, py are pixel coordinates, may be fractional for anti-aliasing."""
        u = (2 * (px / self.image_width) - 1) * self.half_width
        v = (1 - 2 * (py / self.image_height)) * self.half_height
        direction = (self.forward + self.right * u + self.up * v).normalize()
        return Ray(origin=self.origin, direction=direction)
