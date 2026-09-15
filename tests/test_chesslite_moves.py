from chesslite.board import Board
from chesslite.game import Game
from chesslite.moves import (
    legal_moves,
    pseudo_legal_moves,
    apply_move,
    is_in_check,
    make_move,
)


def empty_board(to_move="w"):
    b = Board()
    b.squares = {}
    b.castling = {"wK": False, "wQ": False, "bK": False, "bQ": False}
    b.to_move = to_move
    return b


def test_pawn_double_step_and_blocked():
    b = empty_board()
    b.squares[(4, 1)] = "P"
    b.squares[(4, 0)] = "K"
    b.squares[(4, 7)] = "k"
    moves = pseudo_legal_moves(b, "w")
    targets = {m.to for m in moves if m.frm == (4, 1)}
    assert (4, 2) in targets and (4, 3) in targets

    b.squares[(4, 2)] = "p"
    moves = pseudo_legal_moves(b, "w")
    targets = {m.to for m in moves if m.frm == (4, 1)}
    assert targets == set()  # blocked entirely, even the double-step


def test_pawn_capture_diagonal():
    b = empty_board()
    b.squares[(4, 3)] = "P"
    b.squares[(3, 4)] = "p"
    b.squares[(4, 0)] = "K"
    b.squares[(4, 7)] = "k"
    targets = {m.to for m in pseudo_legal_moves(b, "w") if m.frm == (4, 3)}
    assert (3, 4) in targets


def test_pawn_promotion_generates_four_choices():
    b = empty_board()
    b.squares[(4, 6)] = "P"
    b.squares[(4, 0)] = "K"
    b.squares[(0, 7)] = "k"
    promos = {m.promotion for m in pseudo_legal_moves(b, "w") if m.frm == (4, 6)}
    assert promos == {"Q", "R", "B", "N"}


def test_en_passant_capture_available():
    game = Game()
    game.make_move("e2e4")
    game.make_move("a7a6")
    game.make_move("e4e5")
    game.make_move("d7d5")
    moves = game.legal_moves()
    ep = [m for m in moves if m.frm == (4, 4) and m.en_passant]
    assert len(ep) == 1
    assert ep[0].to == (3, 5)
    game.make_move(ep[0])
    assert game.board.piece_at((3, 4)) is None  # captured black pawn removed
    assert game.board.piece_at((3, 5)) == "P"


def test_knight_moves_from_corner():
    b = empty_board()
    b.squares[(0, 0)] = "N"
    b.squares[(4, 0)] = "K"
    b.squares[(4, 7)] = "k"
    targets = {m.to for m in pseudo_legal_moves(b, "w") if m.frm == (0, 0)}
    assert targets == {(1, 2), (2, 1)}


def test_sliding_piece_blocked_by_own_and_captures_enemy():
    b = empty_board()
    b.squares[(0, 0)] = "R"
    b.squares[(0, 3)] = "p"
    b.squares[(3, 0)] = "P"
    b.squares[(4, 0)] = "K"
    b.squares[(4, 7)] = "k"
    targets = {m.to for m in pseudo_legal_moves(b, "w") if m.frm == (0, 0)}
    assert (0, 1) in targets and (0, 2) in targets and (0, 3) in targets
    assert (0, 4) not in targets  # can't jump past the captured pawn
    assert (1, 0) in targets and (2, 0) in targets
    assert (3, 0) not in targets  # own pawn blocks


def test_king_cannot_move_into_check():
    b = empty_board()
    b.squares[(4, 0)] = "K"
    b.squares[(4, 7)] = "k"
    b.squares[(0, 1)] = "r"  # attacks all of rank 2
    legal = legal_moves(b, "w")
    targets = {m.to for m in legal if m.frm == (4, 0)}
    assert (4, 1) not in targets
    assert (3, 0) in targets and (5, 0) in targets


def test_is_in_check():
    b = empty_board()
    b.squares[(4, 0)] = "K"
    b.squares[(4, 7)] = "k"
    b.squares[(4, 6)] = "r"
    assert is_in_check(b, "w")
    assert not is_in_check(b, "b")


def test_castling_kingside_when_clear():
    b = empty_board()
    b.squares[(4, 0)] = "K"
    b.squares[(7, 0)] = "R"
    b.squares[(4, 7)] = "k"
    b.castling["wK"] = True
    castles = [m for m in legal_moves(b, "w") if m.castle == "K"]
    assert len(castles) == 1
    after = apply_move(b, castles[0])
    assert after.piece_at((6, 0)) == "K"
    assert after.piece_at((5, 0)) == "R"


def test_castling_blocked_by_attacked_square():
    b = empty_board()
    b.squares[(4, 0)] = "K"
    b.squares[(7, 0)] = "R"
    b.squares[(4, 7)] = "k"
    b.squares[(5, 7)] = "r"  # rook attacks f1, the king's pass-through square
    b.castling["wK"] = True
    castles = [m for m in legal_moves(b, "w") if m.castle == "K"]
    assert castles == []


def test_castling_unavailable_without_rights():
    b = empty_board()
    b.squares[(4, 0)] = "K"
    b.squares[(7, 0)] = "R"
    b.squares[(4, 7)] = "k"
    b.castling["wK"] = False
    castles = [m for m in legal_moves(b, "w") if m.castle == "K"]
    assert castles == []


def test_stalemate_classic_position():
    game = Game()
    b = empty_board()
    b.squares[(0, 7)] = "K"  # a8
    b.squares[(2, 6)] = "k"  # c7
    b.squares[(1, 5)] = "q"  # b6
    game.board = b
    assert not game.in_check()
    assert game.legal_moves() == []
    assert game.result() == "stalemate"


def test_foolsmate_checkmate():
    game = Game()
    game.make_move("f2f3")
    game.make_move("e7e5")
    game.make_move("g2g4")
    game.make_move("d8h4")
    assert game.in_check()
    assert game.legal_moves() == []
    assert game.result() == "checkmate"
