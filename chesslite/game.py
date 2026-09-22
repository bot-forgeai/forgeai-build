"""Game: turn order, move parsing, and game-over detection on top of the
pure board/move-generation layer."""
from .board import Board, FILES, parse_square, square_name, color_of, opponent
from .moves import legal_moves, apply_move, is_in_check, Move

PROMO_LETTERS = {"q": "Q", "r": "R", "b": "B", "n": "N"}


class IllegalMoveError(ValueError):
    pass


class Game:
    def __init__(self, board=None):
        self.board = board or Board()
        self.history = []  # list of Move applied so far
        self.san_history = []  # list of SAN strings, parallel to history
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
        san = self.san(move)
        self.board = apply_move(self.board, move)
        self.history.append(move)
        self.san_history.append(san)
        key = self.board.position_key()
        self.position_counts[key] = self.position_counts.get(key, 0) + 1
        return move

    def move_str(self, move: Move) -> str:
        s = f"{square_name(move.frm)}{square_name(move.to)}"
        if move.promotion:
            s += move.promotion.lower()
        return s

    def _disambiguation(self, move: Move) -> str:
        """Minimal file/rank/both prefix needed so this move can't be
        confused with another legal move of the same piece type landing
        on the same target square (standard SAN disambiguation rules)."""
        piece = self.board.piece_at(move.frm)
        others = [
            m
            for m in self.legal_moves()
            if m.to == move.to
            and m.frm != move.frm
            and self.board.piece_at(m.frm) == piece
        ]
        if not others:
            return ""
        frm_file, frm_rank = move.frm
        if not any(m.frm[0] == frm_file for m in others):
            return FILES[frm_file]
        if not any(m.frm[1] == frm_rank for m in others):
            return str(frm_rank + 1)
        return f"{FILES[frm_file]}{frm_rank + 1}"

    def san(self, move: Move) -> str:
        """Standard Algebraic Notation for `move`, assuming self.board is
        the position *before* the move is applied."""
        if move.castle == "K":
            base = "O-O"
        elif move.castle == "Q":
            base = "O-O-O"
        else:
            piece = self.board.piece_at(move.frm)
            is_pawn = piece.upper() == "P"
            is_capture = move.en_passant or self.board.piece_at(move.to) is not None
            if is_pawn:
                prefix = f"{FILES[move.frm[0]]}x" if is_capture else ""
            else:
                prefix = piece.upper() + self._disambiguation(move)
                if is_capture:
                    prefix += "x"
            promo = f"={move.promotion}" if move.promotion else ""
            base = f"{prefix}{square_name(move.to)}{promo}"

        mover = self.board.to_move
        new_board = apply_move(self.board, move)
        opp = opponent(mover)
        if is_in_check(new_board, opp):
            base += "#" if not legal_moves(new_board, opp) else "+"
        return base

    def to_pgn(self, result: str = "*") -> str:
        """Movetext for the game played so far, e.g. '1. e4 e5 2. Nf3 *'."""
        parts = []
        for i, san in enumerate(self.san_history):
            if i % 2 == 0:
                parts.append(f"{i // 2 + 1}.")
            parts.append(san)
        parts.append(result)
        return " ".join(parts)
