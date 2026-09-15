from chesslite.ai import choose_move, evaluate
from chesslite.board import Board
from chesslite.game import Game


def empty_board():
    b = Board()
    b.squares = {}
    b.castling = {"wK": False, "wQ": False, "bK": False, "bQ": False}
    return b


def test_evaluate_starting_position_is_balanced():
    b = Board()
    assert evaluate(b, "w") == 0
    assert evaluate(b, "b") == 0


def test_evaluate_favors_material_advantage():
    b = empty_board()
    b.squares[(4, 0)] = "K"
    b.squares[(4, 7)] = "k"
    b.squares[(0, 0)] = "Q"
    assert evaluate(b, "w") > 0
    assert evaluate(b, "b") < 0


def test_ai_takes_free_undefended_rook():
    b = empty_board()
    b.squares[(4, 0)] = "K"
    b.squares[(4, 7)] = "k"
    b.squares[(0, 0)] = "Q"
    b.squares[(0, 7)] = "r"  # undefended, far from the black king
    move = choose_move(b, "w", depth=2)
    assert move.frm == (0, 0)
    assert move.to == (0, 7)


def test_ai_returns_none_when_no_legal_moves():
    game = Game()
    b = empty_board()
    b.squares[(0, 7)] = "K"
    b.squares[(2, 6)] = "k"
    b.squares[(1, 5)] = "q"
    game.board = b
    assert choose_move(game.board, "w", depth=1) is None


def test_ai_plays_a_full_legal_game_against_itself():
    game = Game()
    moves_played = 0
    while not game.is_over() and moves_played < 30:
        move = choose_move(game.board, game.to_move, depth=1)
        game.make_move(move)
        moves_played += 1
    assert moves_played > 0
