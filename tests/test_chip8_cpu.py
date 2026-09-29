import random

import pytest

from chip8 import asm
from chip8.cpu import CPU, Chip8Error, FONT_START, PROGRAM_START


def make_cpu(instructions, rng=None, on_draw=None):
    cpu = CPU(rng=rng, on_draw=on_draw)
    cpu.load_rom(asm.assemble(instructions))
    return cpu


def run_n(cpu, n):
    for _ in range(n):
        cpu.step()
    return cpu


def test_load_rom_too_large_raises():
    cpu = CPU()
    with pytest.raises(Chip8Error):
        cpu.load_rom(bytes(4096))


def test_ld_vx_byte():
    cpu = make_cpu([asm.ld_vx_byte(3, 0x42)])
    run_n(cpu, 1)
    assert cpu.v[3] == 0x42
    assert cpu.pc == PROGRAM_START + 2


def test_add_vx_byte_wraps():
    cpu = make_cpu([asm.ld_vx_byte(0, 0xFF), asm.add_vx_byte(0, 5)])
    run_n(cpu, 2)
    assert cpu.v[0] == 4


def test_jp():
    cpu = make_cpu([asm.jp(0x300)])
    run_n(cpu, 1)
    assert cpu.pc == 0x300


def test_call_and_ret():
    cpu = make_cpu([
        asm.call(0x300),      # 0x200
        asm.ld_vx_byte(0, 99),  # 0x202: only reached after RET
    ])
    cpu.memory[0x300:0x302] = asm.ret()
    run_n(cpu, 1)  # CALL
    assert cpu.pc == 0x300
    assert cpu.stack == [PROGRAM_START + 2]
    run_n(cpu, 1)  # RET
    assert cpu.pc == PROGRAM_START + 2
    run_n(cpu, 1)  # LD V0, 99
    assert cpu.v[0] == 99


def test_ret_with_empty_stack_raises():
    cpu = make_cpu([asm.ret()])
    with pytest.raises(Chip8Error):
        cpu.step()


def test_call_stack_overflow():
    cpu = CPU()
    instructions = [asm.call(PROGRAM_START)] * 17  # calls itself repeatedly
    cpu.load_rom(asm.assemble(instructions))
    with pytest.raises(Chip8Error):
        for _ in range(17):
            cpu.step()


def test_se_vx_byte_skips_when_equal():
    cpu = make_cpu([
        asm.ld_vx_byte(0, 5),
        asm.se_vx_byte(0, 5),
        asm.ld_vx_byte(1, 111),  # skipped
        asm.ld_vx_byte(2, 222),
    ])
    run_n(cpu, 4)
    assert cpu.v[1] == 0
    assert cpu.v[2] == 222


def test_sne_vx_byte_skips_when_different():
    cpu = make_cpu([
        asm.ld_vx_byte(0, 5),
        asm.sne_vx_byte(0, 9),
        asm.ld_vx_byte(1, 111),  # skipped
    ])
    run_n(cpu, 3)
    assert cpu.v[1] == 0


def test_se_vx_vy():
    cpu = make_cpu([
        asm.ld_vx_byte(0, 7),
        asm.ld_vx_byte(1, 7),
        asm.se_vx_vy(0, 1),
        asm.ld_vx_byte(2, 1),  # skipped
    ])
    run_n(cpu, 4)
    assert cpu.v[2] == 0


def test_sne_vx_vy():
    cpu = make_cpu([
        asm.ld_vx_byte(0, 7),
        asm.ld_vx_byte(1, 8),
        asm.sne_vx_vy(0, 1),
        asm.ld_vx_byte(2, 1),  # skipped
    ])
    run_n(cpu, 4)
    assert cpu.v[2] == 0


@pytest.mark.parametrize("op_name,a,b,expected_vx,expected_vf", [
    ("or_vx_vy", 0b1010, 0b0110, 0b1110, None),
    ("and_vx_vy", 0b1010, 0b0110, 0b0010, None),
    ("xor_vx_vy", 0b1010, 0b0110, 0b1100, None),
])
def test_bitwise_ops(op_name, a, b, expected_vx, expected_vf):
    op = getattr(asm, op_name)
    cpu = make_cpu([asm.ld_vx_byte(0, a), asm.ld_vx_byte(1, b), op(0, 1)])
    run_n(cpu, 3)
    assert cpu.v[0] == expected_vx


def test_ld_vx_vy():
    cpu = make_cpu([asm.ld_vx_byte(1, 55), asm.ld_vx_vy(0, 1)])
    run_n(cpu, 2)
    assert cpu.v[0] == 55


def test_add_vx_vy_sets_carry():
    cpu = make_cpu([asm.ld_vx_byte(0, 250), asm.ld_vx_byte(1, 10), asm.add_vx_vy(0, 1)])
    run_n(cpu, 3)
    assert cpu.v[0] == 4
    assert cpu.v[0xF] == 1


def test_add_vx_vy_no_carry():
    cpu = make_cpu([asm.ld_vx_byte(0, 10), asm.ld_vx_byte(1, 10), asm.add_vx_vy(0, 1)])
    run_n(cpu, 3)
    assert cpu.v[0] == 20
    assert cpu.v[0xF] == 0


def test_sub_vx_vy_no_borrow():
    cpu = make_cpu([asm.ld_vx_byte(0, 10), asm.ld_vx_byte(1, 3), asm.sub_vx_vy(0, 1)])
    run_n(cpu, 3)
    assert cpu.v[0] == 7
    assert cpu.v[0xF] == 1  # VF = NOT borrow


def test_sub_vx_vy_with_borrow():
    cpu = make_cpu([asm.ld_vx_byte(0, 3), asm.ld_vx_byte(1, 10), asm.sub_vx_vy(0, 1)])
    run_n(cpu, 3)
    assert cpu.v[0] == (3 - 10) & 0xFF
    assert cpu.v[0xF] == 0


def test_subn_vx_vy():
    cpu = make_cpu([asm.ld_vx_byte(0, 3), asm.ld_vx_byte(1, 10), asm.subn_vx_vy(0, 1)])
    run_n(cpu, 3)
    assert cpu.v[0] == 7
    assert cpu.v[0xF] == 1


def test_shr_vx():
    cpu = make_cpu([asm.ld_vx_byte(0, 0b101), asm.shr_vx(0)])
    run_n(cpu, 2)
    assert cpu.v[0] == 0b10
    assert cpu.v[0xF] == 1


def test_shl_vx():
    cpu = make_cpu([asm.ld_vx_byte(0, 0b10000001), asm.shl_vx(0)])
    run_n(cpu, 2)
    assert cpu.v[0] == 0b00000010
    assert cpu.v[0xF] == 1


def test_ld_i():
    cpu = make_cpu([asm.ld_i(0x345)])
    run_n(cpu, 1)
    assert cpu.i == 0x345


def test_jp_v0():
    cpu = make_cpu([asm.ld_vx_byte(0, 0x10), asm.jp_v0(0x300)])
    run_n(cpu, 2)
    assert cpu.pc == 0x310


def test_rnd_vx_masks_with_kk():
    cpu = make_cpu([asm.rnd_vx(0, 0x0F)], rng=random.Random(1))
    run_n(cpu, 1)
    assert 0 <= cpu.v[0] <= 0x0F


def test_rnd_vx_deterministic_with_seeded_rng():
    cpu1 = make_cpu([asm.rnd_vx(0, 0xFF)], rng=random.Random(42))
    cpu2 = make_cpu([asm.rnd_vx(0, 0xFF)], rng=random.Random(42))
    run_n(cpu1, 1)
    run_n(cpu2, 1)
    assert cpu1.v[0] == cpu2.v[0]


def test_cls_clears_display():
    cpu = make_cpu([asm.ld_i(FONT_START), asm.ld_vx_byte(0, 0), asm.ld_vx_byte(1, 0), asm.drw(0, 1, 5), asm.cls()])
    run_n(cpu, 4)
    assert any(any(row) for row in cpu.display)
    run_n(cpu, 1)
    assert not any(any(row) for row in cpu.display)


def test_drw_sets_pixels_and_no_collision():
    draws = []
    cpu = make_cpu(
        [asm.ld_i(FONT_START), asm.ld_vx_byte(0, 0), asm.ld_vx_byte(1, 0), asm.drw(0, 1, 5)],
        on_draw=lambda d: draws.append([row[:] for row in d]),
    )
    run_n(cpu, 4)
    assert cpu.v[0xF] == 0
    # font "0" sprite is 0xF0,0x90,0x90,0x90,0xF0 -> top row has 4 lit pixels
    assert cpu.display[0][0:4] == [1, 1, 1, 1]
    assert len(draws) == 1


def test_drw_detects_collision():
    cpu = make_cpu([
        asm.ld_i(FONT_START), asm.ld_vx_byte(0, 0), asm.ld_vx_byte(1, 0), asm.drw(0, 1, 5),
        asm.drw(0, 1, 5),  # drawing the same sprite again XORs it off and sets VF
    ])
    run_n(cpu, 5)
    assert cpu.v[0xF] == 1
    assert not any(any(row) for row in cpu.display)


def test_drw_wraps_around_screen_edges():
    cpu = make_cpu([asm.ld_i(FONT_START), asm.ld_vx_byte(0, 63), asm.ld_vx_byte(1, 0), asm.drw(0, 1, 1)])
    run_n(cpu, 4)
    # font "0" top row 0xF0 = 11110000 -> only the leftmost bit wraps onto column 63
    assert cpu.display[0][63] == 1
    assert cpu.display[0][0] == 1  # second bit wraps to column 0


def test_skp_and_sknp_when_key_not_pressed():
    cpu = make_cpu([
        asm.ld_vx_byte(0, 5),
        asm.skp_vx(0),          # key 5 not pressed -> does NOT skip
        asm.ld_vx_byte(1, 1),   # runs
        asm.sknp_vx(0),         # key 5 not pressed -> DOES skip
        asm.ld_vx_byte(2, 1),   # skipped over
    ])
    run_n(cpu, 3)
    assert cpu.v[1] == 1
    pc_before = cpu.pc
    run_n(cpu, 1)  # SKNP
    assert cpu.pc == pc_before + 4  # advanced past its own instruction *and* the skipped one
    assert cpu.v[2] == 0


def test_skp_skips_when_key_pressed():
    cpu = make_cpu([
        asm.ld_vx_byte(0, 5),
        asm.skp_vx(0),
        asm.ld_vx_byte(1, 1),
    ])
    cpu.press_key(5)
    run_n(cpu, 3)
    assert cpu.v[1] == 0


def test_ld_vx_dt_and_dt_vx():
    cpu = make_cpu([asm.ld_vx_byte(0, 30), asm.ld_dt_vx(0), asm.ld_vx_byte(1, 99), asm.ld_vx_dt(1)])
    run_n(cpu, 4)
    assert cpu.v[1] == 30


def test_ld_st_vx():
    cpu = make_cpu([asm.ld_vx_byte(0, 10), asm.ld_st_vx(0)])
    run_n(cpu, 2)
    assert cpu.sound_timer == 10


def test_add_i_vx():
    cpu = make_cpu([asm.ld_i(0x100), asm.ld_vx_byte(0, 5), asm.add_i_vx(0)])
    run_n(cpu, 3)
    assert cpu.i == 0x105


def test_ld_f_vx_points_at_font_sprite():
    cpu = make_cpu([asm.ld_vx_byte(0, 3), asm.ld_f_vx(0)])
    run_n(cpu, 2)
    assert cpu.i == FONT_START + 3 * 5


def test_ld_b_vx_stores_bcd():
    cpu = make_cpu([asm.ld_i(0x400), asm.ld_vx_byte(0, 234), asm.ld_b_vx(0)])
    run_n(cpu, 3)
    assert list(cpu.memory[0x400:0x403]) == [2, 3, 4]


def test_ld_i_vx_stores_registers_to_memory():
    cpu = make_cpu([
        asm.ld_i(0x400),
        asm.ld_vx_byte(0, 1), asm.ld_vx_byte(1, 2), asm.ld_vx_byte(2, 3),
        asm.ld_i_vx(2),
    ])
    run_n(cpu, 5)
    assert list(cpu.memory[0x400:0x403]) == [1, 2, 3]


def test_ld_vx_i_loads_registers_from_memory():
    cpu = CPU()
    cpu.memory[0x400:0x403] = bytes([7, 8, 9])
    cpu.load_rom(asm.assemble([asm.ld_i(0x400), asm.ld_vx_i(2)]))
    run_n(cpu, 2)
    assert cpu.v[0:3] == [7, 8, 9]


def test_ld_vx_k_waits_for_key():
    cpu = make_cpu([asm.ld_vx_k(3)])
    run_n(cpu, 1)
    assert cpu.waiting_for_key_register == 3
    cpu.step()  # should be a no-op while waiting
    assert cpu.pc == PROGRAM_START + 2  # didn't advance past the LD Vx,K instruction's own PC increment... see press_key
    cpu.press_key(9)
    assert cpu.v[3] == 9
    assert cpu.waiting_for_key_register is None


def test_pc_out_of_bounds_raises():
    cpu = CPU()
    cpu.pc = 4095
    with pytest.raises(Chip8Error):
        cpu.step()


def test_unknown_opcode_raises():
    cpu = CPU()
    cpu.memory[PROGRAM_START] = 0x50
    cpu.memory[PROGRAM_START + 1] = 0x01  # 0x5001, n != 0, invalid 5XYN
    with pytest.raises(Chip8Error):
        cpu.step()


def test_tick_timers_decrements_and_floors_at_zero():
    cpu = CPU()
    cpu.delay_timer = 1
    cpu.sound_timer = 0
    cpu.tick_timers()
    assert cpu.delay_timer == 0
    cpu.tick_timers()
    assert cpu.delay_timer == 0
    assert cpu.sound_timer == 0
