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
    restart_delay: float = 0.0
    depends_on: List[str] = field(default_factory=list)


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
        restart_delay = entry.get("restart_delay", 0.0)
        if not isinstance(restart_delay, (int, float)) or restart_delay < 0:
            raise ConfigError(f"service '{name}' has invalid 'restart_delay' (must be a non-negative number)")
        depends_on = entry.get("depends_on", [])
        if not isinstance(depends_on, list) or not all(isinstance(d, str) for d in depends_on):
            raise ConfigError(f"service '{name}' has invalid 'depends_on' (must be a list of strings)")
        result.append(Service(
            name=name,
            command=command,
            cwd=entry.get("cwd"),
            autorestart=entry.get("autorestart", True),
            max_restarts=entry.get("max_restarts", 5),
            env=entry.get("env", {}),
            restart_delay=restart_delay,
            depends_on=depends_on,
        ))

    names = {s.name for s in result}
    for s in result:
        for dep in s.depends_on:
            if dep == s.name:
                raise ConfigError(f"service '{s.name}' cannot depend on itself")
            if dep not in names:
                raise ConfigError(f"service '{s.name}' depends_on unknown service '{dep}'")

    topological_order(result)  # raises ConfigError on a circular dependency
    return result


def topological_order(services: List[Service]) -> List[Service]:
    """Return services ordered so that each one comes after every
    service it depends_on (Kahn/DFS-style ordering). Raises ConfigError
    if the dependency graph has a cycle."""
    by_name = {s.name: s for s in services}
    state: dict = {}  # name -> "visiting" | "done"
    order: List[Service] = []

    def visit(svc: Service, path: List[str]):
        mark = state.get(svc.name)
        if mark == "done":
            return
        if mark == "visiting":
            cycle = " -> ".join(path + [svc.name])
            raise ConfigError(f"circular dependency: {cycle}")
        state[svc.name] = "visiting"
        for dep in svc.depends_on:
            visit(by_name[dep], path + [svc.name])
        state[svc.name] = "done"
        order.append(svc)

    for s in services:
        visit(s, [])
    return order
