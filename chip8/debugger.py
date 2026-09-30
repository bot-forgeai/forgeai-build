"""An interactive step-through debugger for a CHIP-8 program.

Wraps a `CPU` with breakpoints, single-stepping, and register/memory
inspection, independent of any I/O so it can be driven by a real
terminal or by tests with injected input/output.
"""
from .cpu import MEMORY_SIZE
from .disasm import disassemble_instruction

HELP_TEXT = """\
Commands:
  s, step [n]        execute n instructions (default 1)
  c, continue        run until a breakpoint, halt, or key-wait
  b, break ADDR      set a breakpoint at ADDR (hex like 0x200, or decimal)
  d, delete ADDR     remove a breakpoint
  bp, breakpoints    list breakpoints
  r, regs            dump registers, PC, I, timers, and the stack
  x, mem ADDR [n]    dump n bytes of memory starting at ADDR (default 16)
  l, list [n]        disassemble n upcoming instructions from PC (default 5)
  key N              press key N (0-F), resolving an FX0A key-wait
  h, help            show this text
  q, quit            exit the debugger
"""


class DebuggerCommandError(Exception):
    """Raised for a malformed debugger command."""


def parse_addr(token):
    try:
        return int(token, 16) if token.lower().startswith("0x") else int(token)
    except ValueError:
        raise DebuggerCommandError(f"not a valid address: {token!r}")


def current_instruction(cpu):
    """Return (pc, opcode_or_None, mnemonic) for the instruction about to execute."""
    pc = cpu.pc
    if pc + 1 >= MEMORY_SIZE:
        return pc, None, "<out of bounds>"
    opcode = (cpu.memory[pc] << 8) | cpu.memory[pc + 1]
    return pc, opcode, disassemble_instruction(opcode)


def format_registers(cpu):
    lines = []
    for row_start in range(0, 16, 4):
        row = "  ".join(f"V{j:X}=0x{cpu.v[j]:02X}" for j in range(row_start, row_start + 4))
        lines.append(row)
    lines.append(f"I=0x{cpu.i:03X}  PC=0x{cpu.pc:03X}  DT={cpu.delay_timer}  ST={cpu.sound_timer}")
    stack_str = ", ".join(f"0x{addr:03X}" for addr in cpu.stack)
    lines.append(f"stack=[{stack_str}]")
    return "\n".join(lines)


def format_memory(cpu, addr, length):
    chunk = cpu.memory[addr:addr + length]
    return " ".join(f"{b:02X}" for b in chunk)


def format_listing(cpu, count):
    lines = []
    pc = cpu.pc
    for _ in range(count):
        if pc + 1 >= MEMORY_SIZE:
            break
        opcode = (cpu.memory[pc] << 8) | cpu.memory[pc + 1]
        marker = "-> " if pc == cpu.pc else "   "
        lines.append(f"{marker}0x{pc:04X}: {disassemble_instruction(opcode)}")
        pc += 2
    return "\n".join(lines)


class Debugger:
    """Tracks breakpoints and drives a CPU's step/continue control flow."""

    def __init__(self, cpu):
        self.cpu = cpu
        self.breakpoints = set()

    def step(self):
        """Execute exactly one instruction. No-op (returns False) if blocked or halted."""
        if self.cpu.halted or self.cpu.waiting_for_key_register is not None:
            return False
        self.cpu.step()
        return True

    def run_until_stop(self, max_steps=1_000_000):
        """Step until a breakpoint, halt, or key-wait; or `max_steps` is exhausted.

        Returns one of "breakpoint", "halted", "key-wait", "max-steps".
        """
        for _ in range(max_steps):
            if self.cpu.halted:
                return "halted"
            if self.cpu.waiting_for_key_register is not None:
                return "key-wait"
            self.cpu.step()
            if self.cpu.pc in self.breakpoints:
                return "breakpoint"
        return "max-steps"


def _status_line(cpu):
    pc, _opcode, mnemonic = current_instruction(cpu)
    marker = "[HALTED] " if cpu.halted else "[KEY-WAIT] " if cpu.waiting_for_key_register is not None else ""
    return f"{marker}0x{pc:04X}: {mnemonic}"


def run_repl(cpu, input_fn=input, print_fn=print):
    """Run the interactive debugger loop until `quit` or EOF on `input_fn`."""
    debugger = Debugger(cpu)
    print_fn(_status_line(cpu))
    while True:
        try:
            line = input_fn("(chip8-debug) ")
        except EOFError:
            return
        parts = line.strip().split()
        if not parts:
            continue
        cmd, args = parts[0], parts[1:]
        try:
            if cmd in ("q", "quit"):
                return
            elif cmd in ("h", "help"):
                print_fn(HELP_TEXT.rstrip("\n"))
            elif cmd in ("s", "step"):
                n = int(args[0]) if args else 1
                for _ in range(n):
                    if not debugger.step():
                        break
                print_fn(_status_line(cpu))
            elif cmd in ("c", "continue"):
                reason = debugger.run_until_stop()
                print_fn(f"stopped: {reason}")
                print_fn(_status_line(cpu))
            elif cmd in ("b", "break"):
                if not args:
                    raise DebuggerCommandError("usage: break ADDR")
                addr = parse_addr(args[0])
                debugger.breakpoints.add(addr)
                print_fn(f"breakpoint set at 0x{addr:04X}")
            elif cmd in ("d", "delete"):
                if not args:
                    raise DebuggerCommandError("usage: delete ADDR")
                addr = parse_addr(args[0])
                debugger.breakpoints.discard(addr)
                print_fn(f"breakpoint removed at 0x{addr:04X}")
            elif cmd in ("bp", "breakpoints"):
                if not debugger.breakpoints:
                    print_fn("no breakpoints set")
                else:
                    print_fn(", ".join(f"0x{addr:04X}" for addr in sorted(debugger.breakpoints)))
            elif cmd in ("r", "regs"):
                print_fn(format_registers(cpu))
            elif cmd in ("x", "mem"):
                if not args:
                    raise DebuggerCommandError("usage: mem ADDR [n]")
                addr = parse_addr(args[0])
                length = int(args[1]) if len(args) > 1 else 16
                print_fn(format_memory(cpu, addr, length))
            elif cmd in ("l", "list"):
                count = int(args[0]) if args else 5
                print_fn(format_listing(cpu, count))
            elif cmd == "key":
                if not args:
                    raise DebuggerCommandError("usage: key N")
                key = parse_addr(args[0])
                cpu.press_key(key)
                cpu.release_key(key)
                print_fn(_status_line(cpu))
            else:
                print_fn(f"unknown command: {cmd!r} (try 'help')")
        except DebuggerCommandError as exc:
            print_fn(f"error: {exc}")
