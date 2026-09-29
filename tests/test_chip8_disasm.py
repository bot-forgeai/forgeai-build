from chip8 import asm
from chip8.disasm import disassemble_instruction, disassemble_rom


def test_cls_and_ret():
    assert disassemble_instruction(0x00E0) == "CLS"
    assert disassemble_instruction(0x00EE) == "RET"


def test_jp_and_call():
    assert disassemble_instruction(0x1234) == "JP 0x234"
    assert disassemble_instruction(0x2345) == "CALL 0x345"


def test_ld_vx_byte_and_add():
    assert disassemble_instruction(0x6A12) == "LD VA, 0x12"
    assert disassemble_instruction(0x7A12) == "ADD VA, 0x12"


def test_arithmetic_family():
    assert disassemble_instruction(0x8AB0) == "LD VA, VB"
    assert disassemble_instruction(0x8AB4) == "ADD VA, VB"
    assert disassemble_instruction(0x8AB6) == "SHR VA, VB"


def test_draw_and_random():
    assert disassemble_instruction(0xD125) == "DRW V1, V2, 5"
    assert disassemble_instruction(0xC1FF) == "RND V1, 0xFF"


def test_f_opcodes():
    assert disassemble_instruction(0xF129) == "LD F, V1"
    assert disassemble_instruction(0xF133) == "LD B, V1"
    assert disassemble_instruction(0xF165) == "LD V1, [I]"


def test_unknown_opcode_falls_back_to_dw():
    assert disassemble_instruction(0x5001).startswith("DW ")


def test_disassemble_rom_yields_addresses():
    rom = asm.assemble([asm.cls(), asm.ret()])
    result = list(disassemble_rom(rom))
    assert result == [(0x200, "CLS"), (0x202, "RET")]
