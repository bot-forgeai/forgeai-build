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


def test_console_script_installed():
    result = subprocess.run([sys.executable, "-m", "chip8", "--version"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "chip8" in result.stdout
