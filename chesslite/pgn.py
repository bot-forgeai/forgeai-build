"""PGN movetext parsing: turns the SAN token stream from a .pgn file back
into a sequence of move strings a Game can replay."""
import re

RESULT_TOKENS = {"1-0", "0-1", "1/2-1/2", "*"}
MOVE_NUMBER_RE = re.compile(r"^\d+\.+$")


def parse_pgn_movetext(text: str):
    """Strips `[Tag "value"]` headers, `{...}` comments, and move-number
    markers (`1.` / `1...`) from PGN text, returning the ordered list of
    SAN move tokens. Stops at (and excludes) the result token."""
    text = re.sub(r"\{[^}]*\}", " ", text)
    lines = [
        line for line in text.splitlines() if not line.strip().startswith("[")
    ]
    tokens = " ".join(lines).split()
    moves = []
    for tok in tokens:
        if tok in RESULT_TOKENS:
            break
        if MOVE_NUMBER_RE.match(tok):
            continue
        # A move number can be glued to the move itself, e.g. "1.e4".
        tok = re.sub(r"^\d+\.+", "", tok)
        # Strip NAG-style annotation suffixes like "!", "?", "!?", "??".
        tok = re.sub(r"[!?]+$", "", tok)
        if not tok:
            continue
        moves.append(tok)
    return moves
