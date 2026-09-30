from chip8 import asm
from chip8.cpu import CPU, PROGRAM_START
from chip8.debugger import (
    Debugger,
    current_instruction,
    format_listing,
    format_memory,
    format_registers,
    parse_addr,
    run_repl,
    DebuggerCommandError,
)


def make_cpu(instructions, **quirks):
    cpu = CPU(**quirks)
    cpu.load_rom(asm.assemble(instructions))
    return cpu


def test_parse_addr_hex_and_decimal():
    assert parse_addr("0x200") == 0x200
    assert parse_addr("512") == 512


def test_parse_addr_invalid_raises():
    try:
        parse_addr("nope")
        assert False, "expected DebuggerCommandError"
    except DebuggerCommandError:
        pass


def test_current_instruction_disassembles_next_opcode():
    cpu = make_cpu([asm.ld_vx_byte(0, 0x42)])
    pc, opcode, mnemonic = current_instruction(cpu)
    assert pc == PROGRAM_START
    assert opcode == 0x6042
    assert mnemonic == "LD V0, 0x42"


def test_debugger_step_advances_one_instruction():
    cpu = make_cpu([asm.ld_vx_byte(0, 0x42), asm.ld_vx_byte(1, 0x99)])
    dbg = Debugger(cpu)
    assert dbg.step() is True
    assert cpu.v[0] == 0x42
    assert cpu.v[1] == 0


def test_debugger_step_noop_when_halted():
    cpu = make_cpu([asm.exit_()])
    dbg = Debugger(cpu)
    dbg.step()
    assert cpu.halted
    assert dbg.step() is False


def test_debugger_run_until_stop_hits_breakpoint():
    cpu = make_cpu([
        asm.ld_vx_byte(0, 1),
        asm.ld_vx_byte(1, 2),
        asm.ld_vx_byte(2, 3),
    ])
    dbg = Debugger(cpu)
    target = PROGRAM_START + 4
    dbg.breakpoints.add(target)
    reason = dbg.run_until_stop()
    assert reason == "breakpoint"
    assert cpu.pc == target
    assert cpu.v[0] == 1 and cpu.v[1] == 2 and cpu.v[2] == 0


def test_debugger_run_until_stop_halts():
    cpu = make_cpu([asm.ld_vx_byte(0, 1), asm.exit_()])
    dbg = Debugger(cpu)
    reason = dbg.run_until_stop()
    assert reason == "halted"


def test_debugger_run_until_stop_key_wait():
    cpu = make_cpu([asm.ld_vx_k(3)])
    dbg = Debugger(cpu)
    reason = dbg.run_until_stop()
    assert reason == "key-wait"
    assert cpu.waiting_for_key_register == 3


def test_format_registers_shows_all_v_regs_and_state():
    cpu = make_cpu([asm.ld_vx_byte(0xA, 0x7)])
    cpu.step()
    cpu.i = 0x300
    text = format_registers(cpu)
    assert "VA=0x07" in text
    assert "I=0x300" in text
    assert "PC=0x" in text
    assert "stack=[]" in text


def test_format_memory_dumps_bytes():
    cpu = make_cpu([asm.ld_vx_byte(0, 0x42)])
    text = format_memory(cpu, PROGRAM_START, 2)
    assert text == "60 42"


def test_format_listing_marks_current_pc():
    cpu = make_cpu([asm.ld_vx_byte(0, 1), asm.ld_vx_byte(1, 2)])
    text = format_listing(cpu, 2)
    lines = text.splitlines()
    assert lines[0].startswith("-> ")
    assert lines[1].startswith("   ")
    assert "LD V0, 0x01" in lines[0]
    assert "LD V1, 0x02" in lines[1]


def test_repl_step_and_regs():
    cpu = make_cpu([asm.ld_vx_byte(0, 0x42)])
    inputs = iter(["step", "regs", "quit"])
    outputs = []
    run_repl(cpu, input_fn=lambda prompt: next(inputs), print_fn=outputs.append)
    assert cpu.v[0] == 0x42
    assert any("V0=0x42" in line for line in outputs)


def test_repl_breakpoint_and_continue():
    cpu = make_cpu([
        asm.ld_vx_byte(0, 1),
        asm.ld_vx_byte(1, 2),
        asm.ld_vx_byte(2, 3),
    ])
    target = PROGRAM_START + 4
    inputs = iter([f"break 0x{target:X}", "continue", "quit"])
    outputs = []
    run_repl(cpu, input_fn=lambda prompt: next(inputs), print_fn=outputs.append)
    assert cpu.pc == target
    assert any("stopped: breakpoint" in line for line in outputs)


def test_repl_unblocks_key_wait():
    cpu = make_cpu([asm.ld_vx_k(5)])
    inputs = iter(["continue", "key 7", "quit"])
    outputs = []
    run_repl(cpu, input_fn=lambda prompt: next(inputs), print_fn=outputs.append)
    assert cpu.v[5] == 7
    assert cpu.waiting_for_key_register is None


def test_repl_unknown_command_reports_error():
    cpu = make_cpu([asm.ld_vx_byte(0, 1)])
    inputs = iter(["bogus", "quit"])
    outputs = []
    run_repl(cpu, input_fn=lambda prompt: next(inputs), print_fn=outputs.append)
    assert any("unknown command" in line for line in outputs)


def test_repl_break_without_addr_reports_clean_error():
    cpu = make_cpu([asm.ld_vx_byte(0, 1)])
    inputs = iter(["break", "quit"])
    outputs = []
    run_repl(cpu, input_fn=lambda prompt: next(inputs), print_fn=outputs.append)
    assert any("error: usage: break ADDR" in line for line in outputs)


def test_repl_exits_cleanly_on_eof():
    cpu = make_cpu([asm.ld_vx_byte(0, 1)])

    def raise_eof(prompt):
        raise EOFError

    outputs = []
    run_repl(cpu, input_fn=raise_eof, print_fn=outputs.append)
    assert cpu.v[0] == 0
