"""Move generation and legality checking.

Pseudo-legal moves obey piece movement rules but may leave the mover's
own king in check; legal_moves() filters those out by simulating each
move and checking the resulting position.
"""
from collections import namedtuple

from .board import color_of, opponent

Move = namedtuple("Move", ["frm", "to", "promotion", "en_passant", "castle"])


def make_move(frm, to, promotion=None, en_passant=False, castle=None):
    return Move(frm, to, promotion, en_passant, castle)


KNIGHT_DELTAS = [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)]
KING_DELTAS = [(df, dr) for df in (-1, 0, 1) for dr in (-1, 0, 1) if (df, dr) != (0, 0)]
BISHOP_DIRS = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
ROOK_DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
QUEEN_DIRS = BISHOP_DIRS + ROOK_DIRS


def _on_board(f, r):
    return 0 <= f < 8 and 0 <= r < 8


def _slide_attacks(board, coord, dirs):
    """Squares attacked by a sliding piece at coord, stopping at the first
    occupied square in each direction (inclusive of that square)."""
    f0, r0 = coord
    for df, dr in dirs:
        f, r = f0 + df, r0 + dr
        while _on_board(f, r):
            yield (f, r)
            if (f, r) in board.squares:
                break
            f, r = f + df, r + dr


def attacks_square(board, target, by_color) -> bool:
    """True if any piece of by_color attacks the target square. Uses raw
    attack patterns only (no castling), so it's safe to call while
    generating king moves without recursion."""
    tf, tr = target
    pawn_dir = 1 if by_color == "w" else -1
    for df in (-1, 1):
        src = (tf - df, tr - pawn_dir)
        if board.piece_at(src) == ("P" if by_color == "w" else "p"):
            return True
    knight = "N" if by_color == "w" else "n"
    for df, dr in KNIGHT_DELTAS:
        if board.piece_at((tf - df, tr - dr)) == knight:
            return True
    king = "K" if by_color == "w" else "k"
    for df, dr in KING_DELTAS:
        if board.piece_at((tf - df, tr - dr)) == king:
            return True
    bishop, rook, queen = (
        ("B", "R", "Q") if by_color == "w" else ("b", "r", "q")
    )
    for sq in _slide_attacks(board, target, BISHOP_DIRS):
        p = board.piece_at(sq)
        if p in (bishop, queen):
            return True
    for sq in _slide_attacks(board, target, ROOK_DIRS):
        p = board.piece_at(sq)
        if p in (rook, queen):
            return True
    return False


def _pawn_moves(board, coord, color):
    moves = []
    f, r = coord
    direction = 1 if color == "w" else -1
    start_rank = 1 if color == "w" else 6
    last_rank = 7 if color == "w" else 0
    promo_pieces = ["Q", "R", "B", "N"]

    one_step = (f, r + direction)
    if _on_board(*one_step) and one_step not in board.squares:
        if one_step[1] == last_rank:
            for p in promo_pieces:
                moves.append(make_move(coord, one_step, promotion=p))
        else:
            moves.append(make_move(coord, one_step))
        two_step = (f, r + 2 * direction)
        if r == start_rank and two_step not in board.squares:
            moves.append(make_move(coord, two_step))

    for df in (-1, 1):
        target = (f + df, r + direction)
        if not _on_board(*target):
            continue
        occ = board.piece_at(target)
        if occ is not None and color_of(occ) != color:
            if target[1] == last_rank:
                for p in promo_pieces:
                    moves.append(make_move(coord, target, promotion=p))
            else:
                moves.append(make_move(coord, target))
        elif target == board.en_passant:
            moves.append(make_move(coord, target, en_passant=True))
    return moves


def _knight_moves(board, coord, color):
    moves = []
    f, r = coord
    for df, dr in KNIGHT_DELTAS:
        target = (f + df, r + dr)
        if not _on_board(*target):
            continue
        occ = board.piece_at(target)
        if occ is None or color_of(occ) != color:
            moves.append(make_move(coord, target))
    return moves


def _slide_moves(board, coord, color, dirs):
    moves = []
    for target in _slide_attacks(board, coord, dirs):
        occ = board.piece_at(target)
        if occ is None or color_of(occ) != color:
            moves.append(make_move(coord, target))
    return moves


def _king_moves(board, coord, color):
    moves = []
    f, r = coord
    for df, dr in KING_DELTAS:
        target = (f + df, r + dr)
        if not _on_board(*target):
            continue
        occ = board.piece_at(target)
        if occ is None or color_of(occ) != color:
            moves.append(make_move(coord, target))

    opp = opponent(color)
    home_rank = 0 if color == "w" else 7
    rook = "R" if color == "w" else "r"
    if coord == (4, home_rank) and not attacks_square(board, coord, opp):
        if (
            board.castling.get(color + "K")
            and board.piece_at((7, home_rank)) == rook
            and _castle_path_clear(board, home_rank, (5, 6), opp)
        ):
            moves.append(make_move(coord, (6, home_rank), castle="K"))
        if (
            board.castling.get(color + "Q")
            and board.piece_at((0, home_rank)) == rook
            and _castle_path_clear(board, home_rank, (3, 2), opp, extra_empty=(1,))
        ):
            moves.append(make_move(coord, (2, home_rank), castle="Q"))
    return moves


def _castle_path_clear(board, home_rank, pass_files, opp_color, extra_empty=()):
    for f in pass_files + extra_empty:
        if (f, home_rank) in board.squares:
            return False
    for f in pass_files:
        if attacks_square(board, (f, home_rank), opp_color):
            return False
    return True


def pseudo_legal_moves(board, color):
    moves = []
    for coord, piece in list(board.squares.items()):
        if color_of(piece) != color:
            continue
        ptype = piece.upper()
        if ptype == "P":
            moves.extend(_pawn_moves(board, coord, color))
        elif ptype == "N":
            moves.extend(_knight_moves(board, coord, color))
        elif ptype == "B":
            moves.extend(_slide_moves(board, coord, color, BISHOP_DIRS))
        elif ptype == "R":
            moves.extend(_slide_moves(board, coord, color, ROOK_DIRS))
        elif ptype == "Q":
            moves.extend(_slide_moves(board, coord, color, QUEEN_DIRS))
        elif ptype == "K":
            moves.extend(_king_moves(board, coord, color))
    return moves


def apply_move(board, move):
    b = board.copy()
    color = color_of(b.squares[move.frm])
    piece = b.squares.pop(move.frm)
    b.en_passant = None

    if move.en_passant:
        captured_coord = (move.to[0], move.frm[1])
        b.squares.pop(captured_coord, None)

    if move.promotion:
        piece = move.promotion if color == "w" else move.promotion.lower()

    b.squares[move.to] = piece

    if move.castle:
        home_rank = move.frm[1]
        if move.castle == "K":
            rook = b.squares.pop((7, home_rank))
            b.squares[(5, home_rank)] = rook
        else:
            rook = b.squares.pop((0, home_rank))
            b.squares[(3, home_rank)] = rook

    if piece.upper() == "P" and abs(move.to[1] - move.frm[1]) == 2:
        b.en_passant = (move.frm[0], (move.frm[1] + move.to[1]) // 2)

    if piece.upper() == "K":
        b.castling[color + "K"] = False
        b.castling[color + "Q"] = False
    if move.frm == (0, 0) or move.to == (0, 0):
        b.castling["wQ"] = False
    if move.frm == (7, 0) or move.to == (7, 0):
        b.castling["wK"] = False
    if move.frm == (0, 7) or move.to == (0, 7):
        b.castling["bQ"] = False
    if move.frm == (7, 7) or move.to == (7, 7):
        b.castling["bK"] = False

    is_capture = move.to in board.squares or move.en_passant
    if piece.upper() == "P" or is_capture:
        b.halfmove_clock = 0
    else:
        b.halfmove_clock += 1

    if color == "b":
        b.fullmove += 1
    b.to_move = opponent(color)
    return b


def is_in_check(board, color) -> bool:
    return attacks_square(board, board.king_coord(color), opponent(color))


def legal_moves(board, color):
    result = []
    for move in pseudo_legal_moves(board, color):
        after = apply_move(board, move)
        if not is_in_check(after, color):
            result.append(move)
    return result
