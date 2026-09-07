import pytest

from ttt.board import Board, InvalidMove


def test_valid_moves_alternate_turns():
    b = Board()
    b.make_move("X", 0)
    assert b.turn == "O"
    b.make_move("O", 1)
    assert b.turn == "X"


def test_detects_winner():
    b = Board()
    for symbol, idx in [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)]:
        b.make_move(symbol, idx)
    assert b.winner == "X"
    assert b.is_over()


def test_detects_draw():
    b = Board()
    moves = [
        ("X", 0), ("O", 1), ("X", 2),
        ("O", 4), ("X", 3), ("O", 5),
        ("X", 7), ("O", 6), ("X", 8),
    ]
    for symbol, idx in moves:
        b.make_move(symbol, idx)
    assert b.winner is None
    assert b.is_draw()
    assert b.is_over()


def test_rejects_move_out_of_turn():
    b = Board()
    with pytest.raises(InvalidMove):
        b.make_move("O", 0)


def test_rejects_occupied_cell():
    b = Board()
    b.make_move("X", 0)
    with pytest.raises(InvalidMove):
        b.make_move("O", 0)


def test_rejects_move_after_game_over():
    b = Board()
    for symbol, idx in [("X", 0), ("O", 3), ("X", 1), ("O", 4), ("X", 2)]:
        b.make_move(symbol, idx)
    with pytest.raises(InvalidMove):
        b.make_move("O", 5)


def test_rejects_out_of_range_index():
    b = Board()
    with pytest.raises(InvalidMove):
        b.make_move("X", 9)
