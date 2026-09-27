import json
import subprocess
import sys

import pytest

from raylite.__main__ import main


def write_scene(tmp_path):
    scene = {
        "camera": {"origin": [0, 0, 0]},
        "shapes": [{"type": "sphere", "center": [0, 0, -5], "radius": 1, "material": {"color": [1, 0, 0]}}],
        "lights": [{"position": [5, 5, 0]}],
    }
    path = tmp_path / "scene.json"
    path.write_text(json.dumps(scene))
    return str(path)


def test_render_writes_ppm_file(tmp_path, capsys):
    scene_path = write_scene(tmp_path)
    out_path = tmp_path / "out.ppm"
    rc = main(["render", scene_path, str(out_path), "--width", "8", "--height", "6"])
    assert rc == 0
    assert out_path.read_bytes().startswith(b"P6\n8 6\n255\n")
    captured = capsys.readouterr()
    assert "rendered 8x6" in captured.out


def test_render_missing_scene_file_errors_cleanly(tmp_path, capsys):
    rc = main(["render", str(tmp_path / "nope.json"), str(tmp_path / "out.ppm")])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_render_bad_scene_json_errors_cleanly(tmp_path, capsys):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("not json")
    rc = main(["render", str(bad_path), str(tmp_path / "out.ppm")])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_render_rejects_non_positive_dimensions(tmp_path, capsys):
    scene_path = write_scene(tmp_path)
    rc = main(["render", scene_path, str(tmp_path / "out.ppm"), "--width", "0"])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_render_rejects_non_positive_samples(tmp_path, capsys):
    scene_path = write_scene(tmp_path)
    rc = main(["render", scene_path, str(tmp_path / "out.ppm"), "--samples", "0"])
    assert rc == 1
    assert "error:" in capsys.readouterr().err


def test_version_flag():
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
