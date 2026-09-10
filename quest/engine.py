"""Game engine: interprets parsed commands against a GameState and returns text."""
import random

from .parser import parse

HELP_TEXT = (
    "Commands: go <direction> (or n/s/e/w/u/d), look, take <item>, drop <item>, "
    "inventory, examine <item>, unlock <direction> with <item>, "
    "talk to <person>, give <item> to <person>, quit"
)


class CommandResult:
    def __init__(self, message, quit=False, won=False):
        self.message = message
        self.quit = quit
        self.won = won


def _find_in(item_ids, world, name):
    """Match a typed name against item ids/names in item_ids; substring match, case-insensitive."""
    if not name:
        return None
    name = name.lower()
    for item_id in item_ids:
        item = world["items"][item_id]
        item_name = item.get("name", item_id).lower()
        if name == item_id.lower() or name == item_name or name in item_name:
            return item_id
    return None


def _find_npc_in(npc_ids, world, name):
    """Match a typed name against npc ids/names in npc_ids; substring match, case-insensitive."""
    if not name:
        return None
    name = name.lower()
    for npc_id in npc_ids:
        npc = world["npcs"][npc_id]
        npc_name = npc.get("name", npc_id).lower()
        if name == npc_id.lower() or name == npc_name or name in npc_name:
            return npc_id
    return None


def describe_room(state):
    room = state.room()
    lines = [room.get("name", state.current_room), room.get("description", "")]
    items = room.get("items", [])
    if items:
        names = ", ".join(state.item(i).get("name", i) for i in items)
        lines.append(f"You see: {names}")
    npcs = room.get("npcs", [])
    if npcs:
        names = ", ".join(state.npc(n).get("name", n) for n in npcs)
        lines.append(f"Also here: {names}")
    exits = sorted(room.get("exits", {}).keys())
    if exits:
        locked = room.get("locked_exits", {})
        exit_desc = ", ".join(f"{d} (locked)" if d in locked else d for d in exits)
        lines.append(f"Exits: {exit_desc}")
    return "\n".join(line for line in lines if line)


def _npc_current_room_id(state, npc_id):
    for room_id, room in state.world["rooms"].items():
        if npc_id in room.get("npcs", []):
            return room_id
    return None


def _wander_npcs(state, rng):
    """Move each NPC with a "wander_rooms" list to a random room from that list."""
    for npc_id, npc in state.world.get("npcs", {}).items():
        wander_rooms = npc.get("wander_rooms")
        if not wander_rooms:
            continue
        current_room_id = _npc_current_room_id(state, npc_id)
        if current_room_id is None:
            continue
        destination = rng.choice(wander_rooms)
        if destination == current_room_id or destination not in state.world["rooms"]:
            continue
        state.world["rooms"][current_room_id]["npcs"].remove(npc_id)
        state.world["rooms"][destination].setdefault("npcs", []).append(npc_id)


def _check_win(state):
    """Return the first satisfied win condition (a dict), or None."""
    for win in state.world.get("win", []):
        if state.current_room != win.get("room"):
            continue
        required = win.get("requires_item")
        if required and required not in state.inventory:
            continue
        return win
    return None


def process_command(state, text, rng=None):
    rng = rng or random
    cmd = parse(text)
    if cmd is None:
        return CommandResult("")

    if cmd.verb == "quit":
        return CommandResult("Goodbye.", quit=True)

    if cmd.verb == "help":
        return CommandResult(HELP_TEXT)

    if cmd.verb == "look":
        return CommandResult(describe_room(state))

    if cmd.verb == "inventory":
        if not state.inventory:
            return CommandResult("You are carrying nothing.")
        names = ", ".join(state.item(i).get("name", i) for i in state.inventory)
        return CommandResult(f"You are carrying: {names}")

    if cmd.verb == "go":
        room = state.room()
        direction = cmd.arg
        if not direction:
            return CommandResult("Go where?")
        if direction not in room.get("exits", {}):
            return CommandResult("You can't go that way.")
        if direction in room.get("locked_exits", {}):
            return CommandResult("That way is locked.")
        state.current_room = room["exits"][direction]
        _wander_npcs(state, rng)
        won_condition = _check_win(state)
        message = describe_room(state)
        if won_condition:
            state.flags["won"] = True
            state.flags["ending"] = won_condition.get("id", won_condition.get("room"))
            ending_message = won_condition.get("message")
            if ending_message:
                message = f"{message}\n{ending_message}"
        return CommandResult(message, won=won_condition is not None)

    if cmd.verb == "take":
        room = state.room()
        item_id = _find_in(room.get("items", []), state.world, cmd.arg)
        if item_id is None:
            return CommandResult("There's nothing like that here.")
        item = state.item(item_id)
        if not item.get("takeable", True):
            return CommandResult(f"You can't take the {item.get('name', item_id)}.")
        room["items"].remove(item_id)
        state.inventory.append(item_id)
        return CommandResult(f"You take the {item.get('name', item_id)}.")

    if cmd.verb == "drop":
        item_id = _find_in(state.inventory, state.world, cmd.arg)
        if item_id is None:
            return CommandResult("You aren't carrying that.")
        state.inventory.remove(item_id)
        state.room().setdefault("items", []).append(item_id)
        return CommandResult(f"You drop the {state.item(item_id).get('name', item_id)}.")

    if cmd.verb == "examine":
        room_items = state.room().get("items", [])
        item_id = _find_in(state.inventory, state.world, cmd.arg) or _find_in(room_items, state.world, cmd.arg)
        if item_id is None:
            return CommandResult("You don't see that here.")
        item = state.item(item_id)
        return CommandResult(item.get("description", item.get("name", item_id)))

    if cmd.verb == "unlock":
        direction = cmd.arg
        room = state.room()
        locked = room.get("locked_exits", {})
        if not direction or direction not in locked:
            return CommandResult("There's nothing to unlock that way.")
        item_id = _find_in(state.inventory, state.world, cmd.extra)
        required = locked[direction]
        if item_id != required:
            return CommandResult("That doesn't unlock it.")
        del locked[direction]
        return CommandResult(f"You unlock the way {direction}.")

    if cmd.verb == "talk":
        npc_id = _find_npc_in(state.room().get("npcs", []), state.world, cmd.arg)
        if npc_id is None:
            return CommandResult("There's no one like that here.")
        npc = state.npc(npc_id)
        if npc.get("traded") and npc.get("traded_dialogue"):
            return CommandResult(npc["traded_dialogue"])
        return CommandResult(npc.get("dialogue", "..."))

    if cmd.verb == "give":
        npc_id = _find_npc_in(state.room().get("npcs", []), state.world, cmd.extra)
        if npc_id is None:
            return CommandResult("There's no one like that here.")
        item_id = _find_in(state.inventory, state.world, cmd.arg)
        if item_id is None:
            return CommandResult("You aren't carrying that.")
        npc = state.npc(npc_id)
        wanted = npc.get("wants_item")
        if not wanted or item_id != wanted or npc.get("traded"):
            return CommandResult(f"{npc.get('name', npc_id)} doesn't want that.")
        state.inventory.remove(item_id)
        npc["traded"] = True
        given_item = state.item(item_id).get("name", item_id)
        message = f"You give the {given_item} to {npc.get('name', npc_id)}."
        gives = npc.get("gives_item")
        if gives:
            state.inventory.append(gives)
            message += f" In return, you receive the {state.item(gives).get('name', gives)}."
        return CommandResult(message)

    return CommandResult(f"I don't understand {cmd.arg!r}." if cmd.arg else "I don't understand that.")
