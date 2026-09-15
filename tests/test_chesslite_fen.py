from chesslite.board import Board
from chesslite.fen import from_fen, to_fen
from chesslite.game import Game


def test_starting_position_fen():
    board = Board()
    assert to_fen(board) == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_round_trip_starting_position():
    board = Board()
    restored = from_fen(to_fen(board))
    assert restored.squares == board.squares
    assert restored.to_move == board.to_move
    assert restored.castling == board.castling
    assert restored.en_passant == board.en_passant
    assert restored.halfmove_clock == board.halfmove_clock
    assert restored.fullmove == board.fullmove


def test_round_trip_after_moves_preserves_castling_rights():
    game = Game()
    game.make_move("e2e4")
    game.make_move("e7e5")
    game.make_move("g1f3")
    game.make_move("b8c6")
    game.make_move("f1c4")
    game.make_move("g8f6")
    game.make_move("e1g1")  # white castles kingside

    restored = from_fen(to_fen(game.board))
    assert restored.squares == game.board.squares
    assert restored.castling == {"wK": False, "wQ": False, "bK": True, "bQ": True}


def test_round_trip_preserves_en_passant_target():
    game = Game()
    game.make_move("e2e4")
    game.make_move("a7a6")
    game.make_move("e4e5")
    game.make_move("d7d5")  # sets an en-passant target on d6

    fen = to_fen(game.board)
    assert " d6 " in fen
    restored = from_fen(fen)
    assert restored.en_passant == game.board.en_passant
