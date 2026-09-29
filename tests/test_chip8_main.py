import subprocess
import sys

import pytest

from chip8 import asm
from chip8.__main__ import main


def write_rom(tmp_path, instructions):
    path = tmp_path / "test.ch8"
    path.write_bytes(asm.assemble(instructions))
    return str(path)


def test_run_prints_ascii_display(tmp_path, capsys):
    rom = write_rom(tmp_path, [
        asm.ld_i(0x50), asm.ld_vx_byte(0, 0), asm.ld_vx_byte(1, 0), asm.drw(0, 1, 5),
    ])
    rc = main(["run", rom, "--frames", "1"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "█" in out  # ON_CHAR block appears since the font sprite was drawn


def test_run_missing_rom_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        main(["run", str(tmp_path / "missing.ch8"), "--frames", "1"])


def test_run_reports_cpu_error_cleanly(tmp_path, capsys):
    rom = write_rom(tmp_path, [asm.ret()])  # RET with empty stack
    rc = main(["run", rom, "--frames", "1"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "error:" in err


def test_disasm_command(tmp_path, capsys):
    rom = write_rom(tmp_path, [asm.cls(), asm.jp(0x300)])
    rc = main(["disasm", rom])
    out = capsys.readouterr().out
    assert rc == 0
    assert "0200: CLS" in out
    assert "0202: JP 0x300" in out


def test_play_quits_on_escape_key(tmp_path, monkeypatch):
    import chip8.terminal as terminal

    class DummyRawMode:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(terminal, "RawMode", DummyRawMode)
    monkeypatch.setattr(terminal, "read_available_keys", lambda: ["\x1b"])
    rendered = []
    monkeypatch.setattr(terminal, "clear_and_render", rendered.append)
    monkeypatch.setattr(terminal, "bell", lambda: None)

    rom = write_rom(tmp_path, [asm.cls()])
    rc = main(["play", rom])
    assert rc == 0
    assert rendered == []  # quit before the first frame ever renders


def test_play_stops_after_frame_limit(tmp_path, monkeypatch):
    import chip8.terminal as terminal

    class DummyRawMode:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(terminal, "RawMode", DummyRawMode)
    monkeypatch.setattr(terminal, "read_available_keys", lambda: [])
    rendered = []
    monkeypatch.setattr(terminal, "clear_and_render", rendered.append)
    monkeypatch.setattr(terminal, "bell", lambda: None)

    rom = write_rom(tmp_path, [asm.cls()])
    rc = main(["play", rom, "--frames", "3"])
    assert rc == 0
    assert len(rendered) == 3


def test_play_reports_cpu_error_cleanly(tmp_path, monkeypatch, capsys):
    import chip8.terminal as terminal

    class DummyRawMode:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(terminal, "RawMode", DummyRawMode)
    monkeypatch.setattr(terminal, "read_available_keys", lambda: [])
    monkeypatch.setattr(terminal, "clear_and_render", lambda display: None)
    monkeypatch.setattr(terminal, "bell", lambda: None)

    rom = write_rom(tmp_path, [asm.ret()])  # RET with empty stack
    rc = main(["play", rom, "--frames", "1"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "error:" in err


def test_play_missing_rom_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        main(["play", str(tmp_path / "missing.ch8")])


def test_console_script_installed():
    result = subprocess.run([sys.executable, "-m", "chip8", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "chip8" in result.stdout
