"""A CHIP-8 CPU: memory, registers, stack, timers, and the fetch/decode/execute cycle."""
import random

MEMORY_SIZE = 4096
PROGRAM_START = 0x200
DISPLAY_WIDTH = 64
DISPLAY_HEIGHT = 32
HIRES_DISPLAY_WIDTH = 128
HIRES_DISPLAY_HEIGHT = 64
NUM_REGISTERS = 16
STACK_SIZE = 16
NUM_KEYS = 16
NUM_RPL_FLAGS = 16
SCROLL_PIXELS = 4

FONT_SET = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
    0x20, 0x60, 0x20, 0x20, 0x70,  # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
    0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
    0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
    0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
    0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
    0xF0, 0x80, 0xF0, 0x80, 0x80,  # F
]
FONT_START = 0x50

# Super-CHIP "big font": 16x16 digits 0-9, 10 bytes per glyph (the
# widely-used Octo big-font data, since the original SCHIP spec doesn't
# fix one canonical set of glyph bitmaps).
BIG_FONT_SET = [
    0x3C, 0x7E, 0xE7, 0xC3, 0xC3, 0xC3, 0xC3, 0xE7, 0x7E, 0x3C,  # 0
    0x18, 0x38, 0x58, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x3C,  # 1
    0x3E, 0x7F, 0xC3, 0x06, 0x0C, 0x18, 0x30, 0x60, 0xFF, 0xFF,  # 2
    0x3C, 0x7E, 0xC3, 0x03, 0x0E, 0x0E, 0x03, 0xC3, 0x7E, 0x3C,  # 3
    0x06, 0x0E, 0x1E, 0x36, 0x66, 0xC6, 0xFF, 0xFF, 0x06, 0x06,  # 4
    0xFF, 0xFF, 0xC0, 0xC0, 0xFC, 0xFE, 0x03, 0xC3, 0x7E, 0x3C,  # 5
    0x3E, 0x7C, 0xC0, 0xC0, 0xFC, 0xFE, 0xC3, 0xC3, 0x7E, 0x3C,  # 6
    0xFF, 0xFF, 0x03, 0x06, 0x0C, 0x18, 0x30, 0x60, 0x60, 0x60,  # 7
    0x3C, 0x7E, 0xC3, 0xC3, 0x7E, 0x7E, 0xC3, 0xC3, 0x7E, 0x3C,  # 8
    0x3C, 0x7E, 0xC3, 0xC3, 0x7F, 0x3F, 0x03, 0x03, 0x3E, 0x7C,  # 9
]
BIG_FONT_START = 0xA0


class Chip8Error(Exception):
    """Raised for a malformed ROM or an unimplemented/invalid opcode."""


class CPU:
    """Executes CHIP-8 opcodes against its own memory/register/display state.

    `rng` and `on_draw` are injectable so tests get deterministic RND
    results and can observe display writes without needing a real
    terminal or framebuffer.
    """

    def __init__(self, rng=None, on_draw=None, shift_quirk=True, load_store_quirk=True):
        """`shift_quirk`/`load_store_quirk` default to modern-interpreter behavior.

        Many ROMs (especially original COSMAC VIP-era CHIP-8 programs) were
        written against different semantics for 8XY6/8XYE and FX55/FX65 and
        render incorrectly under the modern defaults - set both to False to
        switch to that classic behavior instead.
        """
        self.memory = bytearray(MEMORY_SIZE)
        self.memory[FONT_START:FONT_START + len(FONT_SET)] = bytes(FONT_SET)
        self.memory[BIG_FONT_START:BIG_FONT_START + len(BIG_FONT_SET)] = bytes(BIG_FONT_SET)
        self.v = [0] * NUM_REGISTERS
        self.i = 0
        self.pc = PROGRAM_START
        self.stack = []
        self.delay_timer = 0
        self.sound_timer = 0
        self.hires = False
        self.display = [[0] * DISPLAY_WIDTH for _ in range(DISPLAY_HEIGHT)]
        self.keys = [False] * NUM_KEYS
        self.waiting_for_key_register = None
        self.rpl_flags = [0] * NUM_RPL_FLAGS
        self._rng = rng or random.Random()
        self._on_draw = on_draw
        self.halted = False
        self.shift_quirk = shift_quirk
        self.load_store_quirk = load_store_quirk

    def load_rom(self, data):
        if len(data) > MEMORY_SIZE - PROGRAM_START:
            raise Chip8Error(f"ROM too large: {len(data)} bytes, max is {MEMORY_SIZE - PROGRAM_START}")
        self.memory[PROGRAM_START:PROGRAM_START + len(data)] = data

    def tick_timers(self):
        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1

    def step(self):
        """Fetch, decode, and execute one instruction. Returns nothing; raises Chip8Error on failure."""
        if self.halted:
            return
        if self.waiting_for_key_register is not None:
            return
        if self.pc + 1 >= MEMORY_SIZE:
            raise Chip8Error(f"program counter out of bounds: 0x{self.pc:04X}")
        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.pc += 2
        self._execute(opcode)

    def _execute(self, opcode):
        nnn = opcode & 0x0FFF
        n = opcode & 0x000F
        x = (opcode & 0x0F00) >> 8
        y = (opcode & 0x00F0) >> 4
        kk = opcode & 0x00FF
        top = (opcode & 0xF000) >> 12

        if opcode == 0x00E0:
            self._clear_display()
        elif opcode == 0x00EE:
            self._ret()
        elif top == 0x0 and (opcode & 0xFFF0) == 0x00C0:
            self._scroll_down(n)
        elif opcode == 0x00FB:
            self._scroll_right()
        elif opcode == 0x00FC:
            self._scroll_left()
        elif opcode == 0x00FD:
            self.halted = True
        elif opcode == 0x00FE:
            self._set_hires(False)
        elif opcode == 0x00FF:
            self._set_hires(True)
        elif top == 0x0:
            pass  # 0NNN (call RCA program) is a no-op on modern interpreters
        elif top == 0x1:
            self.pc = nnn
        elif top == 0x2:
            self._call(nnn)
        elif top == 0x3:
            if self.v[x] == kk:
                self.pc += 2
        elif top == 0x4:
            if self.v[x] != kk:
                self.pc += 2
        elif top == 0x5 and n == 0:
            if self.v[x] == self.v[y]:
                self.pc += 2
        elif top == 0x6:
            self.v[x] = kk
        elif top == 0x7:
            self.v[x] = (self.v[x] + kk) & 0xFF
        elif top == 0x8:
            self._arithmetic(x, y, n)
        elif top == 0x9 and n == 0:
            if self.v[x] != self.v[y]:
                self.pc += 2
        elif top == 0xA:
            self.i = nnn
        elif top == 0xB:
            self.pc = (nnn + self.v[0]) & 0xFFFF
        elif top == 0xC:
            self.v[x] = self._rng.randint(0, 255) & kk
        elif top == 0xD:
            self._draw(x, y, n)
        elif top == 0xE and kk == 0x9E:
            if self.keys[self.v[x] & 0xF]:
                self.pc += 2
        elif top == 0xE and kk == 0xA1:
            if not self.keys[self.v[x] & 0xF]:
                self.pc += 2
        elif top == 0xF:
            self._f_opcode(x, kk)
        else:
            raise Chip8Error(f"unknown opcode: 0x{opcode:04X}")

    def _clear_display(self):
        width, height = self._display_size()
        self.display = [[0] * width for _ in range(height)]

    def _display_size(self):
        if self.hires:
            return HIRES_DISPLAY_WIDTH, HIRES_DISPLAY_HEIGHT
        return DISPLAY_WIDTH, DISPLAY_HEIGHT

    def _set_hires(self, hires):
        self.hires = hires
        self._clear_display()

    def _scroll_down(self, n):
        height = len(self.display)
        width = len(self.display[0]) if height else 0
        blank_rows = [[0] * width for _ in range(min(n, height))]
        self.display = blank_rows + self.display[:height - len(blank_rows)]

    def _scroll_right(self):
        for row in self.display:
            row[:] = [0] * SCROLL_PIXELS + row[:len(row) - SCROLL_PIXELS]

    def _scroll_left(self):
        for row in self.display:
            row[:] = row[SCROLL_PIXELS:] + [0] * SCROLL_PIXELS

    def _ret(self):
        if not self.stack:
            raise Chip8Error("RET with empty call stack")
        self.pc = self.stack.pop()

    def _call(self, nnn):
        if len(self.stack) >= STACK_SIZE:
            raise Chip8Error("CALL: stack overflow")
        self.stack.append(self.pc)
        self.pc = nnn

    def _arithmetic(self, x, y, n):
        vx, vy = self.v[x], self.v[y]
        if n == 0x0:
            self.v[x] = vy
        elif n == 0x1:
            self.v[x] = vx | vy
        elif n == 0x2:
            self.v[x] = vx & vy
        elif n == 0x3:
            self.v[x] = vx ^ vy
        elif n == 0x4:
            result = vx + vy
            self.v[x] = result & 0xFF
            self.v[0xF] = 1 if result > 0xFF else 0
        elif n == 0x5:
            self.v[0xF] = 1 if vx >= vy else 0
            self.v[x] = (vx - vy) & 0xFF
        elif n == 0x6:
            source = vx if self.shift_quirk else vy
            self.v[0xF] = source & 0x1
            self.v[x] = source >> 1
        elif n == 0x7:
            self.v[0xF] = 1 if vy >= vx else 0
            self.v[x] = (vy - vx) & 0xFF
        elif n == 0xE:
            source = vx if self.shift_quirk else vy
            self.v[0xF] = (source & 0x80) >> 7
            self.v[x] = (source << 1) & 0xFF
        else:
            raise Chip8Error(f"unknown 8XY{n:X} opcode")

    def _draw(self, x, y, n):
        width, height = self._display_size()
        origin_x = self.v[x] % width
        origin_y = self.v[y] % height
        self.v[0xF] = 0
        if n == 0:
            # Super-CHIP extended sprite: 16x16, 2 bytes per row, 16 rows.
            for row in range(16):
                sprite_word = (self.memory[self.i + row * 2] << 8) | self.memory[self.i + row * 2 + 1]
                py = (origin_y + row) % height
                for col in range(16):
                    if not (sprite_word & (0x8000 >> col)):
                        continue
                    px = (origin_x + col) % width
                    if self.display[py][px] == 1:
                        self.v[0xF] = 1
                    self.display[py][px] ^= 1
        else:
            for row in range(n):
                sprite_byte = self.memory[self.i + row]
                py = (origin_y + row) % height
                for col in range(8):
                    if not (sprite_byte & (0x80 >> col)):
                        continue
                    px = (origin_x + col) % width
                    if self.display[py][px] == 1:
                        self.v[0xF] = 1
                    self.display[py][px] ^= 1
        if self._on_draw is not None:
            self._on_draw(self.display)

    def _f_opcode(self, x, kk):
        if kk == 0x07:
            self.v[x] = self.delay_timer
        elif kk == 0x0A:
            self.waiting_for_key_register = x
        elif kk == 0x15:
            self.delay_timer = self.v[x]
        elif kk == 0x18:
            self.sound_timer = self.v[x]
        elif kk == 0x1E:
            self.i = (self.i + self.v[x]) & 0xFFFF
        elif kk == 0x29:
            self.i = FONT_START + (self.v[x] & 0xF) * 5
        elif kk == 0x30:
            self.i = BIG_FONT_START + (self.v[x] & 0xF) * 10
        elif kk == 0x33:
            value = self.v[x]
            self.memory[self.i] = value // 100
            self.memory[self.i + 1] = (value // 10) % 10
            self.memory[self.i + 2] = value % 10
        elif kk == 0x55:
            for offset in range(x + 1):
                self.memory[self.i + offset] = self.v[offset]
            if not self.load_store_quirk:
                self.i = (self.i + x + 1) & 0xFFFF
        elif kk == 0x65:
            for offset in range(x + 1):
                self.v[offset] = self.memory[self.i + offset]
            if not self.load_store_quirk:
                self.i = (self.i + x + 1) & 0xFFFF
        elif kk == 0x75:
            for offset in range(x + 1):
                self.rpl_flags[offset % NUM_RPL_FLAGS] = self.v[offset]
        elif kk == 0x85:
            for offset in range(x + 1):
                self.v[offset] = self.rpl_flags[offset % NUM_RPL_FLAGS]
        else:
            raise Chip8Error(f"unknown FX{kk:02X} opcode")

    def press_key(self, key):
        self.keys[key & 0xF] = True
        if self.waiting_for_key_register is not None:
            self.v[self.waiting_for_key_register] = key & 0xF
            self.waiting_for_key_register = None

    def release_key(self, key):
        self.keys[key & 0xF] = False
