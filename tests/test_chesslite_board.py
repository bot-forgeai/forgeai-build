from chesslite.board import Board, parse_square, square_name, color_of, opponent


def test_parse_square_roundtrip():
    for name in ["a1", "h8", "e4", "d5"]:
        assert square_name(parse_square(name)) == name


def test_parse_square_invalid():
    import pytest

    with pytest.raises(ValueError):
        parse_square("i9")
    with pytest.raises(ValueError):
        parse_square("a")


def test_color_of():
    assert color_of("P") == "w"
    assert color_of("p") == "b"


def test_opponent():
    assert opponent("w") == "b"
    assert opponent("b") == "w"


def test_starting_position_piece_count():
    b = Board()
    assert len(b.squares) == 32
    assert b.piece_at((4, 0)) == "K"
    assert b.piece_at((4, 7)) == "k"
    assert b.to_move == "w"


def test_king_coord():
    b = Board()
    assert b.king_coord("w") == (4, 0)
    assert b.king_coord("b") == (4, 7)


def test_copy_is_independent():
    b = Board()
    c = b.copy()
    c.squares[(0, 0)] = "Q"
    assert b.squares[(0, 0)] == "R"


def test_render_shape():
    b = Board()
    text = b.render()
    lines = text.split("\n")
    assert len(lines) == 9  # 8 ranks + file labels
    assert lines[0].startswith("8 ")
    assert lines[-1] == "  a b c d e f g h"
