import json

import pytest

from raylite.scene import SceneError, load_scene, parse_scene
from raylite.shapes import Plane, Sphere, Triangle
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


OBJ_TRIANGLE = "v -1 -1 -5\nv 1 -1 -5\nv 0 1 -5\nf 1 2 3\n"


def test_mesh_shape_loads_relative_to_scene_file(tmp_path):
    (tmp_path / "tri.obj").write_text(OBJ_TRIANGLE)
    data = {
        "camera": {"origin": [0, 0, 0]},
        "shapes": [{"type": "mesh", "file": "tri.obj", "material": {"color": [0, 1, 0]}}],
    }
    scene_path = tmp_path / "scene.json"
    scene_path.write_text(json.dumps(data))
    scene = load_scene(str(scene_path))
    assert len(scene.shapes) == 1
    assert isinstance(scene.shapes[0], Triangle)
    assert scene.shapes[0].material.color == Vec3(0, 1, 0)


def test_mesh_shape_parse_scene_without_base_dir_uses_cwd_relative_path():
    data = {
        "camera": {"origin": [0, 0, 0]},
        "shapes": [{"type": "mesh", "file": "does/not/exist.obj"}],
    }
    with pytest.raises(SceneError):
        parse_scene(data)


def test_mesh_shape_missing_file_field_raises():
    data = {"camera": {"origin": [0, 0, 0]}, "shapes": [{"type": "mesh"}]}
    with pytest.raises(SceneError, match="missing a 'file'"):
        parse_scene(data)


def test_mesh_shape_bad_obj_raises_scene_error(tmp_path):
    (tmp_path / "bad.obj").write_text("v not a number 0\nf 1 2 3\n")
    data = {
        "camera": {"origin": [0, 0, 0]},
        "shapes": [{"type": "mesh", "file": "bad.obj"}],
    }
    scene_path = tmp_path / "scene.json"
    scene_path.write_text(json.dumps(data))
    with pytest.raises(SceneError):
        load_scene(str(scene_path))


def test_mesh_shape_missing_obj_file_raises_scene_error(tmp_path):
    data = {
        "camera": {"origin": [0, 0, 0]},
        "shapes": [{"type": "mesh", "file": "missing.obj"}],
    }
    scene_path = tmp_path / "scene.json"
    scene_path.write_text(json.dumps(data))
    with pytest.raises(SceneError):
        load_scene(str(scene_path))
