"""World model: rooms, items, and a game state loaded from a JSON world file."""
from __future__ import annotations

import json


class WorldError(Exception):
    pass


def load_world(path):
    with open(path) as f:
        data = json.load(f)

    rooms = data.get("rooms")
    if not rooms:
        raise WorldError("world file has no rooms")
    if data.get("start") not in rooms:
        raise WorldError(f"start room {data.get('start')!r} not in rooms")

    for name, room in rooms.items():
        room.setdefault("exits", {})
        room.setdefault("items", [])
        room.setdefault("locked_exits", {})

    items = data.get("items", {})
    return data


class GameState:
    """Mutable state for one playthrough: current room, inventory, flags, visited rooms."""

    def __init__(self, world, current_room=None, inventory=None, flags=None):
        self.world = world
        self.current_room = current_room or world["start"]
        self.inventory = list(inventory) if inventory is not None else []
        self.flags = dict(flags) if flags is not None else {}

    def room(self):
        return self.world["rooms"][self.current_room]

    def item(self, item_id):
        return self.world["items"][item_id]

    def to_dict(self):
        return {
            "current_room": self.current_room,
            "inventory": self.inventory,
            "flags": self.flags,
        }

    @classmethod
    def from_dict(cls, world, data):
        return cls(
            world,
            current_room=data["current_room"],
            inventory=data["inventory"],
            flags=data["flags"],
        )
