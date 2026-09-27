"""3D vector math used throughout the ray tracer."""

from __future__ import annotations

import math
from typing import NamedTuple


class Vec3(NamedTuple):
    x: float
    y: float
    z: float

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __neg__(self) -> "Vec3":
        return Vec3(-self.x, -self.y, -self.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> "Vec3":
        return Vec3(self.x / scalar, self.y / scalar, self.z / scalar)

    def multiply(self, other: "Vec3") -> "Vec3":
        """Component-wise (Hadamard) product, used for tinting colors."""
        return Vec3(self.x * other.x, self.y * other.y, self.z * other.z)

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def length(self) -> float:
        return math.sqrt(self.dot(self))

    def length_squared(self) -> float:
        return self.dot(self)

    def normalize(self) -> "Vec3":
        length = self.length()
        if length == 0:
            return self
        return self / length

    def reflect(self, normal: "Vec3") -> "Vec3":
        """Reflect this vector off a surface with the given unit normal."""
        return self - normal * (2 * self.dot(normal))

    def clamp01(self) -> "Vec3":
        return Vec3(
            min(1.0, max(0.0, self.x)),
            min(1.0, max(0.0, self.y)),
            min(1.0, max(0.0, self.z)),
        )
