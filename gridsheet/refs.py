"""Cell reference parsing and column letter<->number conversion (A=1, Z=26, AA=27, ...)."""
import re

CELL_RE = re.compile(r"^([A-Za-z]+)(\d+)$")


def col_to_num(letters):
    letters = letters.upper()
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def num_to_col(n):
    letters = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return letters


def parse_ref(ref):
    """Return (col_num, row_num) for a cell reference like 'A1', or raise ValueError."""
    m = CELL_RE.match(ref)
    if not m:
        raise ValueError(f"invalid cell reference: {ref!r}")
    return col_to_num(m.group(1)), int(m.group(2))


def normalize_ref(ref):
    """Canonicalize a cell reference's letter case (A1 == a1)."""
    m = CELL_RE.match(ref)
    if not m:
        raise ValueError(f"invalid cell reference: {ref!r}")
    return f"{m.group(1).upper()}{m.group(2)}"


def make_ref(col_num, row_num):
    return f"{num_to_col(col_num)}{row_num}"


def is_ref(token):
    return bool(CELL_RE.match(token))


def expand_range(start_ref, end_ref):
    """List every cell ref in the rectangle spanned by start_ref and end_ref, row-major."""
    c1, r1 = parse_ref(start_ref)
    c2, r2 = parse_ref(end_ref)
    lo_c, hi_c = min(c1, c2), max(c1, c2)
    lo_r, hi_r = min(r1, r2), max(r1, r2)
    refs = []
    for r in range(lo_r, hi_r + 1):
        for c in range(lo_c, hi_c + 1):
            refs.append(make_ref(c, r))
    return refs
