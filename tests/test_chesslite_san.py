from chesslite.board import Board
from chesslite.game import Game


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
