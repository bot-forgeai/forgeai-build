from chip8.terminal import clear_and_render, bell


def test_clear_and_render_writes_ansi_clear_and_ascii(capsys):
    display = [[0] * 64 for _ in range(32)]
    display[0][0] = 1
    clear_and_render(display)
    out = capsys.readouterr().out
    assert "\x1b[2J" in out
    assert "█" in out
    assert "ESC to quit" in out


def test_bell_writes_bell_character(capsys):
    bell()
    out = capsys.readouterr().out
    assert "\a" in out
