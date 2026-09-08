"""Save/load a GameState, including the mutable world (locked_exits, item locations)."""
import json

from .world import GameState


def save_game(state, path, world_path):
    data = {
        "world_path": world_path,
        "world": state.world,
        "state": state.to_dict(),
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_game(path):
    with open(path) as f:
        data = json.load(f)
    world = data["world"]
    state = GameState.from_dict(world, data["state"])
    return state, data.get("world_path")
