import pytest

from chesslite.board import Board
from chesslite.game import Game, IllegalMoveError
from chesslite.pgn import parse_pgn_movetext


def test_pawn_move_san():
    game = Game()
    assert game.san(game.parse_move("e2e4")) == "e4"


def test_knight_move_san():
    game = Game()
    assert game.san(game.parse_move("g1f3")) == "Nf3"


def test_pawn_capture_san_includes_source_file():
    game = Game()
    game.make_move("e2e4")
    game.make_move("d7d5")
    assert game.san(game.parse_move("e4d5")) == "exd5"


def test_piece_capture_san_includes_x():
    game = Game()
    for text in ["e2e4", "d7d5", "e4d5"]:
        game.make_move(text)
    # black recaptures with the queen
    assert game.san(game.parse_move("d8d5")) == "Qxd5"


def test_castling_san():
    board = Board()
    board.squares = {
        (4, 0): "K", (7, 0): "R", (0, 0): "R",
        (4, 7): "k", (7, 7): "r",
    }
    game = Game(board)
    king_side = [m for m in game.legal_moves() if m.castle == "K"][0]
    assert game.san(king_side) == "O-O"
    queen_side = [m for m in game.legal_moves() if m.castle == "Q"][0]
    assert game.san(queen_side) == "O-O-O"


def test_promotion_san():
    board = Board()
    board.squares = {(3, 6): "P", (4, 0): "K", (7, 0): "k"}
    game = Game(board)
    move = game.parse_move("d7d8q")
    assert game.san(move) == "d8=Q"


def test_check_and_checkmate_suffixes():
    # Fool's mate: 1. f3 e5 2. g4 Qh4#
    game = Game()
    game.make_move("f2f3")
    game.make_move("e7e5")
    game.make_move("g2g4")
    move = game.parse_move("d8h4")
    assert game.san(move) == "Qh4#"


def test_disambiguation_by_file():
    board = Board()
    # two white knights that can both reach d2
    board.squares = {(1, 0): "N", (5, 0): "N", (4, 0): "K", (4, 7): "k"}
    game = Game(board)
    move = [m for m in game.legal_moves() if m.frm == (1, 0) and m.to == (3, 1)][0]
    assert game.san(move) == "Nbd2"


def test_disambiguation_by_rank_when_same_file():
    board = Board()
    # two white rooks on the same file, both able to reach d4
    board.squares = {(3, 0): "R", (3, 5): "R", (4, 0): "K", (4, 7): "k"}
    game = Game(board)
    move = [m for m in game.legal_moves() if m.frm == (3, 0) and m.to == (3, 3)][0]
    assert game.san(move) == "R1d4"


def test_san_history_and_to_pgn():
    game = Game()
    game.make_move("e2e4")
    game.make_move("e7e5")
    game.make_move("g1f3")
    assert game.san_history == ["e4", "e5", "Nf3"]
    assert game.to_pgn("*") == "1. e4 e5 2. Nf3 *"


def test_to_pgn_with_result():
    game = Game()
    game.make_move("f2f3")
    game.make_move("e7e5")
    game.make_move("g2g4")
    game.make_move("d8h4")
    assert game.to_pgn("0-1") == "1. f3 e5 2. g4 Qh4# 0-1"


def test_parse_pgn_movetext_strips_numbers_headers_comments_result():
    text = (
        '[Event "Test"]\n'
        '[Result "0-1"]\n\n'
        "1. f3 {a weak opening} e5 2. g4 Qh4# 0-1\n"
    )
    assert parse_pgn_movetext(text) == ["f3", "e5", "g4", "Qh4#"]


def test_parse_pgn_movetext_tolerates_no_space_after_move_number():
    assert parse_pgn_movetext("1.e4 e5 2.Nf3 *") == ["e4", "e5", "Nf3"]


def test_parse_pgn_movetext_strips_nag_annotations():
    assert parse_pgn_movetext("1. e4! e5?! 2. Nf3?? *") == ["e4", "e5", "Nf3"]


def test_push_san_applies_matching_legal_move():
    game = Game()
    game.push_san("e4")
    assert game.san_history == ["e4"]
    assert game.board.piece_at((4, 3)) == "P"


def test_push_san_accepts_zero_castling_notation():
    board = Board()
    board.squares = {(4, 0): "K", (7, 0): "R", (0, 0): "R", (4, 7): "k", (7, 7): "r"}
    game = Game(board)
    game.push_san("0-0")
    assert game.san_history == ["O-O"]


def test_push_san_tolerates_missing_check_marker():
    game = Game()
    for text in ["f2f3", "e7e5", "g2g4"]:
        game.make_move(text)
    game.push_san("Qh4")  # real SAN is "Qh4#"
    assert game.san_history[-1] == "Qh4#"


def test_push_san_rejects_illegal_move():
    game = Game()
    with pytest.raises(IllegalMoveError):
        game.push_san("e5")


def test_game_from_pgn_replays_fools_mate():
    pgn = "1. f3 e5 2. g4 Qh4# 0-1"
    game = Game.from_pgn(pgn)
    assert game.san_history == ["f3", "e5", "g4", "Qh4#"]
    assert game.result() == "checkmate"


def test_game_from_pgn_round_trips_with_to_pgn():
    original = Game()
    for text in ["e2e4", "e7e5", "g1f3"]:
        original.make_move(text)
    pgn = original.to_pgn("*")
    replayed = Game.from_pgn(pgn)
    assert replayed.san_history == original.san_history


def test_game_from_pgn_raises_on_bad_movetext():
    with pytest.raises(IllegalMoveError):
        Game.from_pgn("1. e5 *")
