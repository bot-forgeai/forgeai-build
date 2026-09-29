"""Real-time, interactive CHIP-8 execution: a 60Hz loop with live keyboard input and sound.

Kept separate from any real terminal I/O so it can be driven by fakes in
tests: `read_keys`/`render`/`bell`/`sleep_fn` are all injected.
"""
import time

FRAME_SECONDS = 1 / 60
CYCLES_PER_FRAME = 10
QUIT_KEY = "\x1b"  # ESC

# Standard CHIP-8 keypad (1-9, A-F) mapped onto a QWERTY block, the
# conventional layout used by most terminal/desktop CHIP-8 emulators:
#   1 2 3 C        1 2 3 4
#   4 5 6 D   <-   q w e r
#   7 8 9 E        a s d f
#   A 0 B F        z x c v
KEY_LAYOUT = {
    "1": 0x1, "2": 0x2, "3": 0x3, "4": 0xC,
    "q": 0x4, "w": 0x5, "e": 0x6, "r": 0xD,
    "a": 0x7, "s": 0x8, "d": 0x9, "f": 0xE,
    "z": 0xA, "x": 0x0, "c": 0xB, "v": 0xF,
}


def run_interactive(cpu, read_keys, render, bell, sleep_fn=time.sleep,
                     frame_limit=None, cycles_per_frame=CYCLES_PER_FRAME,
                     frame_seconds=FRAME_SECONDS):
    """Run `cpu` at a fixed 60Hz frame rate until the quit key or `frame_limit` frames.

    `read_keys()` is called once per frame and returns an iterable of
    currently-held key characters; a terminal can't reliably report key-up
    events outside raw mode, so a key not present in a given frame's
    `read_keys()` result is treated as released for that frame — held keys
    must show up in every frame's snapshot to stay "pressed" from the
    emulator's point of view.
    """
    frame = 0
    while frame_limit is None or frame < frame_limit:
        keys = read_keys()
        if QUIT_KEY in keys:
            return
        pressed = set()
        for ch in keys:
            hexkey = KEY_LAYOUT.get(ch.lower())
            if hexkey is not None:
                cpu.press_key(hexkey)
                pressed.add(hexkey)
        for k in range(16):
            if k not in pressed:
                cpu.release_key(k)

        for _ in range(cycles_per_frame):
            cpu.step()
        cpu.tick_timers()
        render(cpu.display)
        if cpu.sound_timer > 0:
            bell()

        sleep_fn(frame_seconds)
        frame += 1
