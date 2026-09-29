"""A tiny helper for building raw CHIP-8 bytecode by hand, used by tests and the bundled sample ROM.

This is not a text assembler with a parser of its own — just Python
functions that pack each instruction family into its 2-byte opcode, so
test programs and the sample ROM can be written as a readable list of
calls instead of raw hex.
"""


def cls():
    return bytes([0x00, 0xE0])


def ret():
    return bytes([0x00, 0xEE])


def jp(nnn):
    return bytes([0x10 | ((nnn >> 8) & 0xF), nnn & 0xFF])


def call(nnn):
    return bytes([0x20 | ((nnn >> 8) & 0xF), nnn & 0xFF])


def se_vx_byte(x, kk):
    return bytes([0x30 | (x & 0xF), kk & 0xFF])


def sne_vx_byte(x, kk):
    return bytes([0x40 | (x & 0xF), kk & 0xFF])


def se_vx_vy(x, y):
    return bytes([0x50 | (x & 0xF), (y & 0xF) << 4])


def ld_vx_byte(x, kk):
    return bytes([0x60 | (x & 0xF), kk & 0xFF])


def add_vx_byte(x, kk):
    return bytes([0x70 | (x & 0xF), kk & 0xFF])


def ld_vx_vy(x, y):
    return bytes([0x80 | (x & 0xF), (y & 0xF) << 4])


def or_vx_vy(x, y):
    return bytes([0x80 | (x & 0xF), ((y & 0xF) << 4) | 0x1])


def and_vx_vy(x, y):
    return bytes([0x80 | (x & 0xF), ((y & 0xF) << 4) | 0x2])


def xor_vx_vy(x, y):
    return bytes([0x80 | (x & 0xF), ((y & 0xF) << 4) | 0x3])


def add_vx_vy(x, y):
    return bytes([0x80 | (x & 0xF), ((y & 0xF) << 4) | 0x4])


def sub_vx_vy(x, y):
    return bytes([0x80 | (x & 0xF), ((y & 0xF) << 4) | 0x5])


def shr_vx(x, y=0):
    return bytes([0x80 | (x & 0xF), ((y & 0xF) << 4) | 0x6])


def subn_vx_vy(x, y):
    return bytes([0x80 | (x & 0xF), ((y & 0xF) << 4) | 0x7])


def shl_vx(x, y=0):
    return bytes([0x80 | (x & 0xF), ((y & 0xF) << 4) | 0xE])


def sne_vx_vy(x, y):
    return bytes([0x90 | (x & 0xF), (y & 0xF) << 4])


def ld_i(nnn):
    return bytes([0xA0 | ((nnn >> 8) & 0xF), nnn & 0xFF])


def jp_v0(nnn):
    return bytes([0xB0 | ((nnn >> 8) & 0xF), nnn & 0xFF])


def rnd_vx(x, kk):
    return bytes([0xC0 | (x & 0xF), kk & 0xFF])


def drw(x, y, n):
    return bytes([0xD0 | (x & 0xF), ((y & 0xF) << 4) | (n & 0xF)])


def skp_vx(x):
    return bytes([0xE0 | (x & 0xF), 0x9E])


def sknp_vx(x):
    return bytes([0xE0 | (x & 0xF), 0xA1])


def ld_vx_dt(x):
    return bytes([0xF0 | (x & 0xF), 0x07])


def ld_vx_k(x):
    return bytes([0xF0 | (x & 0xF), 0x0A])


def ld_dt_vx(x):
    return bytes([0xF0 | (x & 0xF), 0x15])


def ld_st_vx(x):
    return bytes([0xF0 | (x & 0xF), 0x18])


def add_i_vx(x):
    return bytes([0xF0 | (x & 0xF), 0x1E])


def ld_f_vx(x):
    return bytes([0xF0 | (x & 0xF), 0x29])


def ld_b_vx(x):
    return bytes([0xF0 | (x & 0xF), 0x33])


def ld_i_vx(x):
    return bytes([0xF0 | (x & 0xF), 0x55])


def ld_vx_i(x):
    return bytes([0xF0 | (x & 0xF), 0x65])


def assemble(instructions):
    """Concatenate a list of instruction byte-pairs (and/or raw bytes objects) into one ROM."""
    return b"".join(instructions)
