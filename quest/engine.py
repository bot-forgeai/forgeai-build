"""Game engine: interprets parsed commands against a GameState and returns text."""
from .parser import parse

HELP_TEXT = (
    "Commands: go <direction> (or n/s/e/w/u/d), look, take <item>, drop <item>, "
    "inventory, examine <item>, unlock <direction> with <item>, quit"
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


def describe_room(state):
    room = state.room()
    lines = [room.get("name", state.current_room), room.get("description", "")]
    items = room.get("items", [])
    if items:
        names = ", ".join(state.item(i).get("name", i) for i in items)
        lines.append(f"You see: {names}")
    exits = sorted(room.get("exits", {}).keys())
    if exits:
        locked = room.get("locked_exits", {})
        exit_desc = ", ".join(f"{d} (locked)" if d in locked else d for d in exits)
        lines.append(f"Exits: {exit_desc}")
    return "\n".join(line for line in lines if line)


def _check_win(state):
    win = state.world.get("win")
    if not win:
        return False
    if state.current_room != win.get("room"):
        return False
    required = win.get("requires_item")
    if required and required not in state.inventory:
        return False
    return True


def process_command(state, text):
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
        won = _check_win(state)
        if won:
            state.flags["won"] = True
        return CommandResult(describe_room(state), won=won)

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

    return CommandResult(f"I don't understand {cmd.arg!r}." if cmd.arg else "I don't understand that.")
