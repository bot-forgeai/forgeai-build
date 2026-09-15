"""A minimax AI opponent with alpha-beta pruning and a simple material +
mobility evaluation. Not a strong engine, just a working opponent."""
from .board import color_of, opponent
from .moves import legal_moves, apply_move, is_in_check

PIECE_VALUES = {"P": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}

# Small positional bonus for controlling the center, indexed [file][rank].
_CENTER_BONUS = {(3, 3): 10, (3, 4): 10, (4, 3): 10, (4, 4): 10}


def evaluate(board, color) -> int:
    """Positive scores favor `color`."""
    score = 0
    for coord, piece in board.squares.items():
        value = PIECE_VALUES[piece.upper()] + _CENTER_BONUS.get(coord, 0)
        score += value if color_of(piece) == color else -value
    return score


def choose_move(board, color, depth=2):
    """Returns the best legal move for `color` at the given search depth,
    or None if there are no legal moves."""
    moves = legal_moves(board, color)
    if not moves:
        return None

    best_move = None
    best_score = float("-inf")
    alpha, beta = float("-inf"), float("inf")
    for move in moves:
        after = apply_move(board, move)
        score = -_negamax(after, opponent(color), depth - 1, -beta, -alpha)
        if score > best_score:
            best_score = score
            best_move = move
        alpha = max(alpha, score)
    return best_move


def _negamax(board, to_move, depth, alpha, beta):
    moves = legal_moves(board, to_move)
    if not moves:
        if is_in_check(board, to_move):
            # Checkmate: worse the sooner it's found for the side to move.
            return -100000 - depth
        return 0  # stalemate

    if depth == 0:
        return evaluate(board, to_move)

    best = float("-inf")
    for move in moves:
        after = apply_move(board, move)
        score = -_negamax(after, opponent(to_move), depth - 1, -beta, -alpha)
        best = max(best, score)
        alpha = max(alpha, score)
        if alpha >= beta:
            break
    return best
