import json

import pytest

from raylite.scene import SceneError, load_scene, parse_scene
from raylite.shapes import Plane, Sphere
from raylite.vec3 import Vec3

MINIMAL = {
    "camera": {"origin": [0, 0, 0]},
    "shapes": [
        {"type": "sphere", "center": [0, 0, -5], "radius": 1, "material": {"color": [1, 0, 0]}},
        {"type": "plane", "point": [0, -1, 0], "normal": [0, 1, 0], "material": {"color": [0.5, 0.5, 0.5]}},
    ],
    "lights": [{"position": [0, 5, 0]}],
}


def test_parse_minimal_scene():
    scene = parse_scene(MINIMAL)
    assert scene.camera.origin == Vec3(0, 0, 0)
    assert len(scene.shapes) == 2
    assert isinstance(scene.shapes[0], Sphere)
    assert isinstance(scene.shapes[1], Plane)
    assert len(scene.lights) == 1
    assert scene.lights[0].color == Vec3(1, 1, 1)


def test_camera_defaults():
    scene = parse_scene(MINIMAL)
    assert scene.camera.look_at == Vec3(0, 0, -1)
    assert scene.camera.fov_degrees == 60.0


def test_light_radius_defaults_to_zero_hard_shadow():
    scene = parse_scene(MINIMAL)
    assert scene.lights[0].radius == 0.0


def test_light_radius_parsed_from_scene():
    data = json.loads(json.dumps(MINIMAL))
    data["lights"][0]["radius"] = 2.5
    scene = parse_scene(data)
    assert scene.lights[0].radius == 2.5


def test_negative_light_radius_raises():
    data = json.loads(json.dumps(MINIMAL))
    data["lights"][0]["radius"] = -1.0
    with pytest.raises(SceneError):
        parse_scene(data)


def test_missing_camera_raises():
    with pytest.raises(SceneError):
        parse_scene({"shapes": []})


def test_unknown_shape_type_raises():
    data = {"camera": {"origin": [0, 0, 0]}, "shapes": [{"type": "cube"}]}
    with pytest.raises(SceneError):
        parse_scene(data)


def test_missing_required_field_raises():
    data = {"camera": {}}
    with pytest.raises(SceneError):
        parse_scene(data)


def test_load_scene_from_file(tmp_path):
    path = tmp_path / "scene.json"
    path.write_text(json.dumps(MINIMAL))
    scene = load_scene(str(path))
    assert len(scene.shapes) == 2


def test_load_scene_missing_file_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        load_scene(str(tmp_path / "nope.json"))


def test_load_scene_bad_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")
    with pytest.raises(SceneError):
        load_scene(str(path))
