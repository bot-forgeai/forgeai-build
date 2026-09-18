"""Load procman service definitions from a JSON config file."""
import json
from dataclasses import dataclass, field
from typing import List, Optional


class ConfigError(Exception):
    pass


@dataclass
class Service:
    name: str
    command: List[str]
    cwd: Optional[str] = None
    autorestart: bool = True
    max_restarts: int = 5
    env: dict = field(default_factory=dict)


def load_config(path: str) -> List[Service]:
    try:
        with open(path) as f:
            data = json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}")
    except json.JSONDecodeError as e:
        raise ConfigError(f"invalid JSON in {path}: {e}")

    if not isinstance(data, dict) or "services" not in data:
        raise ConfigError("config must be a JSON object with a 'services' list")

    services = data["services"]
    if not isinstance(services, list) or not services:
        raise ConfigError("'services' must be a non-empty list")

    seen = set()
    result = []
    for i, entry in enumerate(services):
        if not isinstance(entry, dict):
            raise ConfigError(f"services[{i}] must be an object")
        name = entry.get("name")
        command = entry.get("command")
        if not name or not isinstance(name, str):
            raise ConfigError(f"services[{i}] missing a string 'name'")
        if name in seen:
            raise ConfigError(f"duplicate service name: {name}")
        seen.add(name)
        if not command or not isinstance(command, list) or not all(isinstance(c, str) for c in command):
            raise ConfigError(f"service '{name}' missing a non-empty 'command' list of strings")
        result.append(Service(
            name=name,
            command=command,
            cwd=entry.get("cwd"),
            autorestart=entry.get("autorestart", True),
            max_restarts=entry.get("max_restarts", 5),
            env=entry.get("env", {}),
        ))
    return result
