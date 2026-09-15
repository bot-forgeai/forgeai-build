"""FEN (Forsyth-Edwards Notation) serialization for Board.

Used by the network protocol (server.py) so a client can reconstruct the
exact board state -- including castling rights and the en-passant target,
not just piece placement -- without replaying the whole move history.
"""
from .board import Board, square_name, parse_square

FILES = "abcdefgh"


def to_fen(board) -> str:
    rows = []
    for r in range(7, -1, -1):
        row = ""
        empty = 0
        for f in range(8):
            piece = board.squares.get((f, r))
            if piece is None:
                empty += 1
                continue
            if empty:
                row += str(empty)
                empty = 0
            row += piece
        if empty:
            row += str(empty)
        rows.append(row)
    placement = "/".join(rows)

    castling = ""
    if board.castling["wK"]:
        castling += "K"
    if board.castling["wQ"]:
        castling += "Q"
    if board.castling["bK"]:
        castling += "k"
    if board.castling["bQ"]:
        castling += "q"
    castling = castling or "-"

    ep = square_name(board.en_passant) if board.en_passant else "-"

    return f"{placement} {board.to_move} {castling} {ep} {board.halfmove_clock} {board.fullmove}"


def from_fen(fen: str) -> Board:
    placement, active, castling, ep, halfmove, fullmove = fen.split()

    board = Board.__new__(Board)
    board.squares = {}
    for r, row in enumerate(reversed(placement.split("/"))):
        f = 0
        for ch in row:
            if ch.isdigit():
                f += int(ch)
            else:
                board.squares[(f, r)] = ch
                f += 1

    board.to_move = active
    board.castling = {
        "wK": "K" in castling,
        "wQ": "Q" in castling,
        "bK": "k" in castling,
        "bQ": "q" in castling,
    }
    board.en_passant = parse_square(ep) if ep != "-" else None
    board.halfmove_clock = int(halfmove)
    board.fullmove = int(fullmove)
    return board
