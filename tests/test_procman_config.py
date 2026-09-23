import json

import pytest

from procman.config import ConfigError, Service, load_config, topological_order


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


def test_restart_delay_defaults_to_zero(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"]}]
    })
    services = load_config(path)
    assert services[0].restart_delay == 0.0


def test_restart_delay_loaded(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"], "restart_delay": 2.5}]
    })
    services = load_config(path)
    assert services[0].restart_delay == 2.5


def test_negative_restart_delay_rejected(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"], "restart_delay": -1}]
    })
    with pytest.raises(ConfigError):
        load_config(path)


def test_non_numeric_restart_delay_rejected(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"], "restart_delay": "soon"}]
    })
    with pytest.raises(ConfigError):
        load_config(path)


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


def test_depends_on_defaults_to_empty(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"]}]
    })
    services = load_config(path)
    assert services[0].depends_on == []


def test_depends_on_loaded_and_forward_reference_allowed(tmp_path):
    path = write_config(tmp_path, {
        "services": [
            {"name": "web", "command": ["sleep", "1"], "depends_on": ["db"]},
            {"name": "db", "command": ["sleep", "1"]},
        ]
    })
    services = load_config(path)
    web = next(s for s in services if s.name == "web")
    assert web.depends_on == ["db"]


def test_depends_on_invalid_type(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"], "depends_on": "db"}]
    })
    with pytest.raises(ConfigError, match="depends_on"):
        load_config(path)


def test_depends_on_unknown_service(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"], "depends_on": ["ghost"]}]
    })
    with pytest.raises(ConfigError, match="unknown service"):
        load_config(path)


def test_depends_on_self(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"], "depends_on": ["a"]}]
    })
    with pytest.raises(ConfigError, match="cannot depend on itself"):
        load_config(path)


def test_depends_on_direct_cycle(tmp_path):
    path = write_config(tmp_path, {
        "services": [
            {"name": "a", "command": ["sleep", "1"], "depends_on": ["b"]},
            {"name": "b", "command": ["sleep", "1"], "depends_on": ["a"]},
        ]
    })
    with pytest.raises(ConfigError, match="circular dependency"):
        load_config(path)


def test_depends_on_longer_cycle(tmp_path):
    path = write_config(tmp_path, {
        "services": [
            {"name": "a", "command": ["sleep", "1"], "depends_on": ["b"]},
            {"name": "b", "command": ["sleep", "1"], "depends_on": ["c"]},
            {"name": "c", "command": ["sleep", "1"], "depends_on": ["a"]},
        ]
    })
    with pytest.raises(ConfigError, match="circular dependency"):
        load_config(path)


def test_topological_order_diamond():
    a = Service(name="a", command=["x"])
    b = Service(name="b", command=["x"], depends_on=["a"])
    c = Service(name="c", command=["x"], depends_on=["a"])
    d = Service(name="d", command=["x"], depends_on=["b", "c"])
    order = topological_order([d, c, b, a])
    names = [s.name for s in order]
    assert names.index("a") < names.index("b")
    assert names.index("a") < names.index("c")
    assert names.index("b") < names.index("d")
    assert names.index("c") < names.index("d")


def test_topological_order_no_deps_preserves_list():
    a = Service(name="a", command=["x"])
    b = Service(name="b", command=["x"])
    order = topological_order([a, b])
    assert [s.name for s in order] == ["a", "b"]


def test_ready_check_defaults_to_none(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"]}]
    })
    services = load_config(path)
    assert services[0].ready_check is None


def test_ready_check_tcp_loaded(tmp_path):
    path = write_config(tmp_path, {
        "services": [{
            "name": "a", "command": ["sleep", "1"],
            "ready_check": {"type": "tcp", "port": 8080},
        }]
    })
    services = load_config(path)
    rc = services[0].ready_check
    assert rc["type"] == "tcp"
    assert rc["port"] == 8080


def test_ready_check_command_loaded(tmp_path):
    path = write_config(tmp_path, {
        "services": [{
            "name": "a", "command": ["sleep", "1"],
            "ready_check": {"type": "command", "command": ["true"]},
        }]
    })
    services = load_config(path)
    assert services[0].ready_check["command"] == ["true"]


def test_ready_check_not_an_object_rejected(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"], "ready_check": "soon"}]
    })
    with pytest.raises(ConfigError, match="ready_check"):
        load_config(path)


def test_ready_check_invalid_type_rejected(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"],
                      "ready_check": {"type": "http", "port": 80}}]
    })
    with pytest.raises(ConfigError, match="type"):
        load_config(path)


def test_ready_check_tcp_missing_port_rejected(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"],
                      "ready_check": {"type": "tcp"}}]
    })
    with pytest.raises(ConfigError, match="port"):
        load_config(path)


def test_ready_check_command_missing_command_rejected(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"],
                      "ready_check": {"type": "command"}}]
    })
    with pytest.raises(ConfigError, match="command"):
        load_config(path)


def test_ready_check_non_positive_timeout_rejected(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"],
                      "ready_check": {"type": "tcp", "port": 80, "timeout": 0}}]
    })
    with pytest.raises(ConfigError, match="timeout"):
        load_config(path)


def test_ready_check_accepted_without_explicit_timeout_or_interval(tmp_path):
    # timeout/interval are optional; the supervisor applies its own
    # defaults (10.0s / 0.2s) when they're absent from the dict.
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"],
                      "ready_check": {"type": "tcp", "port": 80}}]
    })
    services = load_config(path)
    assert "timeout" not in services[0].ready_check
    assert "interval" not in services[0].ready_check


def test_max_log_bytes_accepted(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"], "max_log_bytes": 1024}]
    })
    services = load_config(path)
    assert services[0].max_log_bytes == 1024


def test_max_log_bytes_defaults_to_none(tmp_path):
    path = write_config(tmp_path, {"services": [{"name": "a", "command": ["sleep", "1"]}]})
    services = load_config(path)
    assert services[0].max_log_bytes is None


def test_max_log_bytes_zero_rejected(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"], "max_log_bytes": 0}]
    })
    with pytest.raises(ConfigError, match="max_log_bytes"):
        load_config(path)


def test_max_log_bytes_non_integer_rejected(tmp_path):
    path = write_config(tmp_path, {
        "services": [{"name": "a", "command": ["sleep", "1"], "max_log_bytes": "big"}]
    })
    with pytest.raises(ConfigError, match="max_log_bytes"):
        load_config(path)
