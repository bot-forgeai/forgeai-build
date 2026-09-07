from ttt.ai import choose_move


def test_takes_immediate_win():
    cells = list("XX.......")
    cells[3] = "O"
    cells[4] = "O"
    # X: 0,1 filled, O: 3,4 filled. X should complete the top row at 2.
    assert choose_move(cells, "X") == 2


def test_blocks_opponent_win():
    cells = list(".........")
    cells[0] = "O"
    cells[1] = "O"
    cells[3] = "X"
    # O threatens to win at 2; X must block there.
    assert choose_move(cells, "X") == 2


def test_first_move_on_empty_board_is_valid():
    cells = list(".........")
    move = choose_move(cells, "X")
    assert 0 <= move <= 8


def test_two_perfect_players_always_draw():
    cells = list(".........")
    symbol = "X"
    for _ in range(9):
        if "." not in cells:
            break
        move = choose_move(cells, symbol)
        assert cells[move] == "."
        cells[move] = symbol
        symbol = "O" if symbol == "X" else "X"
    from ttt.board import WIN_LINES

    winner = None
    for a, b, c in WIN_LINES:
        if cells[a] != "." and cells[a] == cells[b] == cells[c]:
            winner = cells[a]
    assert winner is None
    assert "." not in cells
