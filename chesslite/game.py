"""Game: turn order, move parsing, and game-over detection on top of the
pure board/move-generation layer."""
from .board import Board, parse_square, square_name, color_of
from .moves import legal_moves, apply_move, is_in_check, Move

PROMO_LETTERS = {"q": "Q", "r": "R", "b": "B", "n": "N"}


class IllegalMoveError(ValueError):
    pass


class Game:
    def __init__(self, board=None):
        self.board = board or Board()
        self.history = []  # list of Move applied so far
        self.position_counts = {self.board.position_key(): 1}

    @property
    def to_move(self):
        return self.board.to_move

    def legal_moves(self):
        return legal_moves(self.board, self.board.to_move)

    def in_check(self, color=None) -> bool:
        return is_in_check(self.board, color or self.board.to_move)

    def result(self):
        """Returns one of: None (ongoing), 'checkmate', 'stalemate',
        'draw' (50-move rule, threefold repetition, or insufficient
        material)."""
        if not self.legal_moves():
            return "checkmate" if self.in_check() else "stalemate"
        if self.board.halfmove_clock >= 100:
            return "draw"
        if self.position_counts.get(self.board.position_key(), 0) >= 3:
            return "draw"
        if self.board.has_insufficient_material():
            return "draw"
        return None

    def is_over(self) -> bool:
        return self.result() is not None

    def parse_move(self, text: str) -> Move:
        """Parses coordinate notation like 'e2e4' or 'e7e8q' (promotion)."""
        text = text.strip().replace("-", "").replace("=", "")
        if len(text) not in (4, 5):
            raise IllegalMoveError(f"unrecognized move syntax: {text!r}")
        try:
            frm = parse_square(text[0:2])
            to = parse_square(text[2:4])
        except ValueError as exc:
            raise IllegalMoveError(str(exc)) from exc
        promotion = None
        if len(text) == 5:
            letter = text[4].lower()
            if letter not in PROMO_LETTERS:
                raise IllegalMoveError(f"unrecognized promotion piece: {text[4]!r}")
            promotion = PROMO_LETTERS[letter]

        for move in self.legal_moves():
            if move.frm == frm and move.to == to:
                if move.promotion and move.promotion != (promotion or "Q"):
                    continue
                return move
        raise IllegalMoveError(f"illegal move: {text}")

    def make_move(self, move_or_text):
        move = (
            move_or_text
            if isinstance(move_or_text, Move)
            else self.parse_move(move_or_text)
        )
        if move not in self.legal_moves():
            raise IllegalMoveError(f"illegal move: {move}")
        self.board = apply_move(self.board, move)
        self.history.append(move)
        key = self.board.position_key()
        self.position_counts[key] = self.position_counts.get(key, 0) + 1
        return move

    def move_str(self, move: Move) -> str:
        s = f"{square_name(move.frm)}{square_name(move.to)}"
        if move.promotion:
            s += move.promotion.lower()
        return s
