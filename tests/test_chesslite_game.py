import pytest

from chesslite.game import Game, IllegalMoveError


def test_starting_legal_move_count():
    game = Game()
    assert len(game.legal_moves()) == 20  # 16 pawn moves + 4 knight moves


def test_make_move_updates_turn():
    game = Game()
    game.make_move("e2e4")
    assert game.to_move == "b"
    assert game.board.piece_at((4, 3)) == "P"
    assert game.board.piece_at((4, 1)) is None


def test_illegal_move_syntax_raises():
    game = Game()
    with pytest.raises(IllegalMoveError):
        game.parse_move("zz99")
    with pytest.raises(IllegalMoveError):
        game.parse_move("e2")


def test_illegal_move_semantics_raises():
    game = Game()
    with pytest.raises(IllegalMoveError):
        game.make_move("e2e5")  # pawns can't jump three squares


def test_move_str_roundtrip():
    game = Game()
    move = game.parse_move("e2e4")
    assert game.move_str(move) == "e2e4"


def test_promotion_move_str_and_parse():
    from chesslite.board import Board

    game = Game(Board())
    game.board.squares = {(4, 6): "P", (4, 0): "K", (0, 7): "k"}
    move = game.parse_move("e7e8q")
    assert move.promotion == "Q"
    assert game.move_str(move) == "e7e8q"
    game.make_move(move)
    assert game.board.piece_at((4, 7)) == "Q"


def test_draw_by_fifty_move_rule():
    game = Game()
    game.board.halfmove_clock = 100
    assert game.result() == "draw"


def test_ongoing_result_is_none():
    game = Game()
    assert game.result() is None
    assert not game.is_over()
