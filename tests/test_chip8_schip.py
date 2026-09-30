"""Super-CHIP (SCHIP) extension opcodes: hi-res mode, scrolling, big sprites, RPL flags."""
from chip8 import asm
from chip8.cpu import (
    CPU, PROGRAM_START, DISPLAY_WIDTH, DISPLAY_HEIGHT,
    HIRES_DISPLAY_WIDTH, HIRES_DISPLAY_HEIGHT, BIG_FONT_START,
)


def make_cpu(instructions, **quirks):
    cpu = CPU(**quirks)
    cpu.load_rom(asm.assemble(instructions))
    return cpu


def run_n(cpu, n):
    for _ in range(n):
        cpu.step()
    return cpu


def test_high_enables_hires_and_clears():
    cpu = make_cpu([asm.high()])
    cpu.display[0][0] = 1
    run_n(cpu, 1)
    assert cpu.hires is True
    assert len(cpu.display) == HIRES_DISPLAY_HEIGHT
    assert len(cpu.display[0]) == HIRES_DISPLAY_WIDTH
    assert cpu.display[0][0] == 0


def test_low_disables_hires_and_clears():
    cpu = make_cpu([asm.high(), asm.low()])
    run_n(cpu, 2)
    assert cpu.hires is False
    assert len(cpu.display) == DISPLAY_HEIGHT
    assert len(cpu.display[0]) == DISPLAY_WIDTH


def test_exit_halts_execution():
    cpu = make_cpu([asm.exit_(), asm.ld_vx_byte(0, 42)])
    run_n(cpu, 5)  # extra steps should be no-ops once halted
    assert cpu.halted is True
    assert cpu.v[0] == 0
    assert cpu.pc == PROGRAM_START + 2  # advanced past EXIT itself, then frozen


def test_scroll_down():
    cpu = make_cpu([asm.scd(2)])
    cpu.display[0][3] = 1
    run_n(cpu, 1)
    assert cpu.display[2][3] == 1
    assert cpu.display[0][3] == 0


def test_scroll_down_clamped_to_display_height():
    # SCD's N is a single nibble at the opcode level (max 15), always
    # smaller than any real display height - exercise the defensive
    # clamp directly by calling the helper with an out-of-range count.
    cpu = make_cpu([])
    cpu.display[0][0] = 1
    cpu._scroll_down(200)
    assert all(pixel == 0 for row in cpu.display for pixel in row)


def test_scroll_right():
    cpu = make_cpu([asm.scr()])
    cpu.display[0][0] = 1
    run_n(cpu, 1)
    assert cpu.display[0][4] == 1
    assert cpu.display[0][0] == 0


def test_scroll_left():
    cpu = make_cpu([asm.scl()])
    cpu.display[0][4] = 1
    run_n(cpu, 1)
    assert cpu.display[0][0] == 1
    assert cpu.display[0][4] == 0


def test_extended_16x16_sprite_draw():
    cpu = make_cpu([asm.high(), asm.ld_i(0x300), asm.drw(0, 0, 0)])
    # A 16x16 sprite: top-left 2x2 block of set bits, rest zero.
    sprite = bytearray(32)
    sprite[0] = 0xC0  # top row: bits 15,14 set (leftmost 2 pixels)
    sprite[2] = 0xC0  # second row: same
    cpu.memory[0x300:0x300 + 32] = sprite
    run_n(cpu, 3)
    assert cpu.display[0][0] == 1
    assert cpu.display[0][1] == 1
    assert cpu.display[1][0] == 1
    assert cpu.display[1][1] == 1
    assert cpu.display[0][2] == 0


def test_extended_sprite_collision_sets_vf():
    cpu = make_cpu([asm.high(), asm.ld_i(0x300), asm.drw(0, 0, 0), asm.drw(0, 0, 0)])
    sprite = bytearray(32)
    sprite[0] = 0x80
    cpu.memory[0x300:0x300 + 32] = sprite
    run_n(cpu, 3)
    assert cpu.v[0xF] == 0
    run_n(cpu, 1)
    assert cpu.v[0xF] == 1
    assert cpu.display[0][0] == 0  # XORed back off


def test_ld_hf_vx_points_at_big_font_digit():
    cpu = make_cpu([asm.ld_vx_byte(0, 3), asm.ld_hf_vx(0)])
    run_n(cpu, 2)
    assert cpu.i == BIG_FONT_START + 3 * 10


def test_rpl_flags_save_and_load_round_trip():
    cpu = make_cpu([
        asm.ld_vx_byte(0, 11), asm.ld_vx_byte(1, 22), asm.ld_vx_byte(2, 33),
        asm.ld_r_vx(2),
        asm.ld_vx_byte(0, 0), asm.ld_vx_byte(1, 0), asm.ld_vx_byte(2, 0),
        asm.ld_vx_r(2),
    ])
    run_n(cpu, 8)
    assert cpu.v[0:3] == [11, 22, 33]
    assert cpu.rpl_flags[0:3] == [11, 22, 33]


def test_draw_wraps_within_hires_bounds():
    cpu = make_cpu([asm.high(), asm.ld_vx_byte(0, 127), asm.ld_vx_byte(1, 0),
                     asm.ld_i(0x300), asm.drw(0, 1, 1)])
    cpu.memory[0x300] = 0xC0  # bits 7,6 set: pixel at x, x+1 (wraps to 0)
    run_n(cpu, 5)
    assert cpu.display[0][127] == 1
    assert cpu.display[0][0] == 1
