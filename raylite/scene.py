"""Scene loading: parses a JSON scene description into shapes/lights/camera."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, List, Optional

from raylite.shapes import Material, Plane, Sphere
from raylite.vec3 import Vec3


class SceneError(ValueError):
    pass


@dataclass
class Light:
    position: Vec3
    color: Vec3
    intensity: float = 1.0


@dataclass
class Camera:
    origin: Vec3
    look_at: Vec3
    up: Vec3
    fov_degrees: float = 60.0


@dataclass
class Scene:
    camera: Camera
    shapes: List[Any]
    lights: List[Light]
    background: Vec3
    ambient: float = 0.1


def _vec3(data, field: str, default=None) -> Vec3:
    if field not in data:
        if default is not None:
            return default
        raise SceneError(f"missing required field '{field}'")
    value = data[field]
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise SceneError(f"field '{field}' must be a 3-element array")
    return Vec3(float(value[0]), float(value[1]), float(value[2]))


def _material(data: dict) -> Material:
    return Material(
        color=_vec3(data, "color"),
        diffuse=float(data.get("diffuse", 0.8)),
        specular=float(data.get("specular", 0.2)),
        shininess=float(data.get("shininess", 32.0)),
        reflectivity=float(data.get("reflectivity", 0.0)),
    )


def parse_scene(data: dict) -> Scene:
    if "camera" not in data:
        raise SceneError("scene is missing a 'camera'")
    cam_data = data["camera"]
    camera = Camera(
        origin=_vec3(cam_data, "origin"),
        look_at=_vec3(cam_data, "look_at", Vec3(0, 0, -1)),
        up=_vec3(cam_data, "up", Vec3(0, 1, 0)),
        fov_degrees=float(cam_data.get("fov_degrees", 60.0)),
    )

    shapes = []
    for shape_data in data.get("shapes", []):
        kind = shape_data.get("type")
        if kind == "sphere":
            shapes.append(
                Sphere(
                    center=_vec3(shape_data, "center"),
                    radius=float(shape_data["radius"]),
                    material=_material(shape_data.get("material", {})),
                )
            )
        elif kind == "plane":
            shapes.append(
                Plane(
                    point=_vec3(shape_data, "point"),
                    normal=_vec3(shape_data, "normal"),
                    material=_material(shape_data.get("material", {})),
                )
            )
        else:
            raise SceneError(f"unknown shape type: {kind!r}")

    lights = []
    for light_data in data.get("lights", []):
        lights.append(
            Light(
                position=_vec3(light_data, "position"),
                color=_vec3(light_data, "color", Vec3(1, 1, 1)),
                intensity=float(light_data.get("intensity", 1.0)),
            )
        )

    background = _vec3(data, "background", Vec3(0, 0, 0))
    ambient = float(data.get("ambient", 0.1))

    return Scene(camera=camera, shapes=shapes, lights=lights, background=background, ambient=ambient)


def load_scene(path: str) -> Scene:
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as exc:
            raise SceneError(f"invalid JSON: {exc}") from exc
    return parse_scene(data)
