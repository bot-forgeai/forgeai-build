import json

import pytest

from procman.config import ConfigError, load_config


def write_config(tmp_path, data):
    path = tmp_path / "procman.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_load_valid_config(tmp_path):
    path = write_config(tmp_path, {
        "services": [
            {"name": "a", "command": ["sleep", "1"]},
            {"name": "b", "command": ["echo", "hi"], "autorestart": False, "max_restarts": 2},
        ]
    })
    services = load_config(path)
    assert len(services) == 2
    assert services[0].name == "a"
    assert services[0].autorestart is True
    assert services[0].max_restarts == 5
    assert services[1].autorestart is False
    assert services[1].max_restarts == 2


def test_missing_file():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/procman.json")


def test_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json")
    with pytest.raises(ConfigError, match="invalid JSON"):
        load_config(str(path))


def test_missing_services_key(tmp_path):
    path = write_config(tmp_path, {"foo": "bar"})
    with pytest.raises(ConfigError, match="services"):
        load_config(path)


def test_empty_services(tmp_path):
    path = write_config(tmp_path, {"services": []})
    with pytest.raises(ConfigError, match="non-empty"):
        load_config(path)


def test_service_missing_name(tmp_path):
    path = write_config(tmp_path, {"services": [{"command": ["echo", "hi"]}]})
    with pytest.raises(ConfigError, match="name"):
        load_config(path)


def test_service_missing_command(tmp_path):
    path = write_config(tmp_path, {"services": [{"name": "a"}]})
    with pytest.raises(ConfigError, match="command"):
        load_config(path)


def test_duplicate_service_name(tmp_path):
    path = write_config(tmp_path, {
        "services": [
            {"name": "a", "command": ["sleep", "1"]},
            {"name": "a", "command": ["sleep", "2"]},
        ]
    })
    with pytest.raises(ConfigError, match="duplicate"):
        load_config(path)


def test_env_and_cwd(tmp_path):
    path = write_config(tmp_path, {
        "services": [
            {"name": "a", "command": ["sleep", "1"], "cwd": "/tmp", "env": {"X": "1"}},
        ]
    })
    services = load_config(path)
    assert services[0].cwd == "/tmp"
    assert services[0].env == {"X": "1"}
