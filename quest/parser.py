"""Command parsing: turns free text into a (verb, argument) pair."""

DIRECTIONS = {
    "north": "north", "n": "north",
    "south": "south", "s": "south",
    "east": "east", "e": "east",
    "west": "west", "w": "west",
    "up": "up", "u": "up",
    "down": "down", "d": "down",
}

VERB_ALIASES = {
    "go": "go", "move": "go", "walk": "go",
    "look": "look", "l": "look",
    "take": "take", "get": "take", "grab": "take",
    "drop": "drop",
    "inventory": "inventory", "i": "inventory", "inv": "inventory",
    "examine": "examine", "x": "examine", "inspect": "examine",
    "unlock": "unlock",
    "quit": "quit", "exit": "quit",
    "help": "help",
}


class ParsedCommand:
    def __init__(self, verb, arg=None, extra=None):
        self.verb = verb
        self.arg = arg
        self.extra = extra


def parse(text):
    """Parse a raw input line into a ParsedCommand, or None if empty."""
    words = text.strip().lower().split()
    if not words:
        return None

    first = words[0]
    if first in DIRECTIONS:
        return ParsedCommand("go", DIRECTIONS[first])

    verb = VERB_ALIASES.get(first)
    if verb is None:
        return ParsedCommand("unknown", first)

    rest = words[1:]
    if verb == "go":
        if not rest:
            return ParsedCommand("go", None)
        direction = DIRECTIONS.get(rest[0], rest[0])
        return ParsedCommand("go", direction)

    if verb == "unlock":
        # "unlock <direction> with <item words...>"
        if "with" in rest:
            idx = rest.index("with")
            direction_words = rest[:idx]
            item_words = rest[idx + 1:]
        else:
            direction_words = rest
            item_words = []
        direction = DIRECTIONS.get(direction_words[0], " ".join(direction_words)) if direction_words else None
        item = " ".join(item_words) if item_words else None
        return ParsedCommand("unlock", direction, item)

    if verb in ("take", "drop", "examine"):
        return ParsedCommand(verb, " ".join(rest) if rest else None)

    return ParsedCommand(verb, " ".join(rest) if rest else None)
