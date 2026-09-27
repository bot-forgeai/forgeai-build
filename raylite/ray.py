"""A ray: an origin point plus a (typically normalized) direction."""

from __future__ import annotations

from typing import NamedTuple

from raylite.vec3 import Vec3


class Ray(NamedTuple):
    origin: Vec3
    direction: Vec3

    def at(self, t: float) -> Vec3:
        return self.origin + self.direction * t
