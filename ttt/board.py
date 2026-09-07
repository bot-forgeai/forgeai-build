"""Pure tic-tac-toe game logic, independent of any networking."""

WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),
    (0, 3, 6), (1, 4, 7), (2, 5, 8),
    (0, 4, 8), (2, 4, 6),
]


class InvalidMove(Exception):
    pass


class Board:
    def __init__(self):
        self.cells = ["."] * 9
        self.turn = "X"
        self.winner = None

    def render(self):
        return "".join(self.cells)

    def make_move(self, symbol, index):
        if self.winner is not None:
            raise InvalidMove("game already over")
        if symbol != self.turn:
            raise InvalidMove(f"not {symbol}'s turn")
        if not 0 <= index <= 8:
            raise InvalidMove("index out of range")
        if self.cells[index] != ".":
            raise InvalidMove("cell already taken")
        self.cells[index] = symbol
        self.winner = self._check_winner()
        self.turn = "O" if self.turn == "X" else "X"

    def _check_winner(self):
        for a, b, c in WIN_LINES:
            if self.cells[a] != "." and self.cells[a] == self.cells[b] == self.cells[c]:
                return self.cells[a]
        return None

    def is_draw(self):
        return self.winner is None and "." not in self.cells

    def is_over(self):
        return self.winner is not None or self.is_draw()
