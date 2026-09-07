"""Minimax AI for tic-tac-toe. Pure function over board state, no I/O."""

from .board import WIN_LINES


def _winner(cells):
    for a, b, c in WIN_LINES:
        if cells[a] != "." and cells[a] == cells[b] == cells[c]:
            return cells[a]
    return None


def _minimax(cells, symbol, ai_symbol, depth):
    winner = _winner(cells)
    if winner == ai_symbol:
        return 10 - depth
    if winner is not None:
        return depth - 10
    if "." not in cells:
        return 0

    other = "O" if symbol == "X" else "X"
    scores = []
    for i in range(9):
        if cells[i] == ".":
            cells[i] = symbol
            scores.append(_minimax(cells, other, ai_symbol, depth + 1))
            cells[i] = "."
    return max(scores) if symbol == ai_symbol else min(scores)


def choose_move(cells, symbol):
    """Return the best cell index (0-8) for `symbol` to play next.

    Plays perfectly: wins when a win is forced, blocks the opponent
    otherwise, and prefers faster wins / slower losses among equal outcomes.
    """
    cells = list(cells)
    other = "O" if symbol == "X" else "X"
    best_score = None
    best_index = None
    for i in range(9):
        if cells[i] == ".":
            cells[i] = symbol
            score = _minimax(cells, other, symbol, 1)
            cells[i] = "."
            if best_score is None or score > best_score:
                best_score = score
                best_index = i
    return best_index
