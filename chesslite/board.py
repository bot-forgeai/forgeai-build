"""Board representation: piece placement, castling rights, en passant state.

Squares are (file, rank) coordinate pairs, both 0-7, with (0, 0) = a1.
Pieces are single characters: uppercase for white, lowercase for black
('P', 'N', 'B', 'R', 'Q', 'K' / 'p', 'n', 'b', 'r', 'q', 'k').
"""
import copy

FILES = "abcdefgh"


def parse_square(s: str) -> tuple:
    if len(s) != 2 or s[0] not in FILES or s[1] not in "12345678":
        raise ValueError(f"invalid square: {s!r}")
    return (FILES.index(s[0]), int(s[1]) - 1)


def square_name(coord: tuple) -> str:
    f, r = coord
    return f"{FILES[f]}{r + 1}"


def color_of(piece: str) -> str:
    return "w" if piece.isupper() else "b"


def opponent(color: str) -> str:
    return "b" if color == "w" else "w"


_START_RANK = ["R", "N", "B", "Q", "K", "B", "N", "R"]


class Board:
    def __init__(self):
        self.squares = {}
        self.to_move = "w"
        # castling rights keyed "wK"/"wQ"/"bK"/"bQ" (kingside/queenside)
        self.castling = {"wK": True, "wQ": True, "bK": True, "bQ": True}
        self.en_passant = None  # target square coord capturable this move, or None
        self.halfmove_clock = 0
        self.fullmove = 1
        self._setup_start()

    def _setup_start(self):
        for f in range(8):
            self.squares[(f, 0)] = _START_RANK[f]
            self.squares[(f, 1)] = "P"
            self.squares[(f, 6)] = "p"
            self.squares[(f, 7)] = _START_RANK[f].lower()

    def piece_at(self, coord):
        return self.squares.get(coord)

    def king_coord(self, color: str):
        target = "K" if color == "w" else "k"
        for coord, piece in self.squares.items():
            if piece == target:
                return coord
        raise ValueError(f"no king on board for color {color!r}")

    def copy(self) -> "Board":
        new = Board.__new__(Board)
        new.squares = dict(self.squares)
        new.to_move = self.to_move
        new.castling = dict(self.castling)
        new.en_passant = self.en_passant
        new.halfmove_clock = self.halfmove_clock
        new.fullmove = self.fullmove
        return new

    def render(self) -> str:
        lines = []
        for r in range(7, -1, -1):
            row = [self.squares.get((f, r), ".") for f in range(8)]
            lines.append(f"{r + 1} " + " ".join(row))
        lines.append("  " + " ".join(FILES))
        return "\n".join(lines)

    def position_key(self):
        """Hashable snapshot of everything that makes two positions
        the same for repetition purposes: piece placement, side to
        move, castling rights, and en-passant target square."""
        pieces = tuple(sorted(self.squares.items()))
        castling = tuple(sorted(self.castling.items()))
        return (pieces, self.to_move, castling, self.en_passant)

    def has_insufficient_material(self) -> bool:
        """True when neither side has enough material to deliver
        checkmate: K vs K, K+minor vs K, or K+B vs K+B with
        same-colored bishops."""
        pieces = [p for p in self.squares.values() if p not in ("K", "k")]
        if not pieces:
            return True
        if len(pieces) > 2:
            return False
        if any(p.upper() in ("P", "R", "Q") for p in pieces):
            return False
        if len(pieces) == 1:
            return True  # K+minor vs K
        # two minors left: only a same-colored bishop pair is a draw
        if any(p.upper() == "N" for p in pieces):
            return False
        bishop_squares = [
            coord for coord, p in self.squares.items() if p.upper() == "B"
        ]
        colors = {(f + r) % 2 for f, r in bishop_squares}
        return len(colors) == 1
