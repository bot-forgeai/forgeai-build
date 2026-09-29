"""Disassemble raw CHIP-8 bytecode back into readable mnemonics, for inspecting a ROM without running it."""

PROGRAM_START = 0x200


def disassemble_instruction(opcode):
    nnn = opcode & 0x0FFF
    n = opcode & 0x000F
    x = (opcode & 0x0F00) >> 8
    y = (opcode & 0x00F0) >> 4
    kk = opcode & 0x00FF
    top = (opcode & 0xF000) >> 12

    if opcode == 0x00E0:
        return "CLS"
    if opcode == 0x00EE:
        return "RET"
    if top == 0x0:
        return f"SYS 0x{nnn:03X}"
    if top == 0x1:
        return f"JP 0x{nnn:03X}"
    if top == 0x2:
        return f"CALL 0x{nnn:03X}"
    if top == 0x3:
        return f"SE V{x:X}, 0x{kk:02X}"
    if top == 0x4:
        return f"SNE V{x:X}, 0x{kk:02X}"
    if top == 0x5 and n == 0:
        return f"SE V{x:X}, V{y:X}"
    if top == 0x6:
        return f"LD V{x:X}, 0x{kk:02X}"
    if top == 0x7:
        return f"ADD V{x:X}, 0x{kk:02X}"
    if top == 0x8:
        names = {0x0: "LD", 0x1: "OR", 0x2: "AND", 0x3: "XOR", 0x4: "ADD",
                  0x5: "SUB", 0x6: "SHR", 0x7: "SUBN", 0xE: "SHL"}
        if n in names:
            return f"{names[n]} V{x:X}, V{y:X}"
        return f"DW 0x{opcode:04X}"
    if top == 0x9 and n == 0:
        return f"SNE V{x:X}, V{y:X}"
    if top == 0xA:
        return f"LD I, 0x{nnn:03X}"
    if top == 0xB:
        return f"JP V0, 0x{nnn:03X}"
    if top == 0xC:
        return f"RND V{x:X}, 0x{kk:02X}"
    if top == 0xD:
        return f"DRW V{x:X}, V{y:X}, {n}"
    if top == 0xE and kk == 0x9E:
        return f"SKP V{x:X}"
    if top == 0xE and kk == 0xA1:
        return f"SKNP V{x:X}"
    if top == 0xF:
        f_names = {
            0x07: f"LD V{x:X}, DT", 0x0A: f"LD V{x:X}, K", 0x15: f"LD DT, V{x:X}",
            0x18: f"LD ST, V{x:X}", 0x1E: f"ADD I, V{x:X}", 0x29: f"LD F, V{x:X}",
            0x33: f"LD B, V{x:X}", 0x55: f"LD [I], V{x:X}", 0x65: f"LD V{x:X}, [I]",
        }
        if kk in f_names:
            return f_names[kk]
    return f"DW 0x{opcode:04X}"


def disassemble_rom(data):
    """Yield (address, mnemonic) pairs for each 2-byte instruction in a ROM's bytes."""
    for offset in range(0, len(data) - 1, 2):
        opcode = (data[offset] << 8) | data[offset + 1]
        yield PROGRAM_START + offset, disassemble_instruction(opcode)
