"""Real terminal I/O for `chip8 play`: raw-mode key polling and ANSI rendering.

Deliberately thin and untested-by-unit-test (it talks to a real tty) —
all the actual emulation-loop logic lives in interactive.py, which takes
these as injected callables so it can be tested without a terminal.
"""
import sys
import select
import termios
import tty

from .render import to_ascii


class RawMode:
    """Puts stdin into cbreak mode for the duration of a `with` block.

    Cbreak (not full raw) still lets Ctrl-C raise KeyboardInterrupt
    normally, so an emulator that hangs can always be killed.
    """

    def __enter__(self):
        self._fd = sys.stdin.fileno()
        self._old = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        return self

    def __exit__(self, exc_type, exc, tb):
        termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old)
        return False


def read_available_keys():
    """Return every character currently buffered on stdin, without blocking."""
    chars = []
    while select.select([sys.stdin], [], [], 0)[0]:
        chars.append(sys.stdin.read(1))
    return chars


def clear_and_render(display):
    sys.stdout.write("\x1b[H\x1b[2J")
    sys.stdout.write(to_ascii(display))
    sys.stdout.write("\n(ESC to quit)\n")
    sys.stdout.flush()


def bell():
    sys.stdout.write("\a")
    sys.stdout.flush()
