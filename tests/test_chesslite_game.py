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


def test_draw_by_threefold_repetition():
    game = Game()
    # Shuffle both knights out and back twice, returning to the exact
    # starting position (same side to move, same castling rights) a
    # third time (the start itself counts as the first occurrence).
    cycle = ["g1f3", "g8f6", "f3g1", "f6g8"]
    for _ in range(2):
        for move in cycle:
            game.make_move(move)
    assert game.result() == "draw"


def test_no_repetition_draw_before_third_occurrence():
    game = Game()
    cycle = ["g1f3", "g8f6", "f3g1", "f6g8"]
    for move in cycle:
        game.make_move(move)
    assert game.result() is None


def test_draw_by_insufficient_material_king_vs_king():
    from chesslite.board import Board

    game = Game(Board())
    game.board.squares = {(0, 0): "K", (7, 7): "k"}
    assert game.result() == "draw"


def test_draw_by_insufficient_material_king_and_bishop_vs_king():
    from chesslite.board import Board

    game = Game(Board())
    game.board.squares = {(0, 0): "K", (7, 7): "k", (2, 2): "B"}
    assert game.result() == "draw"


def test_not_insufficient_material_with_rook():
    from chesslite.board import Board

    game = Game(Board())
    game.board.squares = {(0, 0): "K", (7, 7): "k", (2, 2): "R"}
    assert game.result() is None
