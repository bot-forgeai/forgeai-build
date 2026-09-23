"""Cell reference parsing and column letter<->number conversion (A=1, Z=26, AA=27, ...).

A reference may optionally lock its column and/or row with a '$' prefix, e.g.
'$A1' (column locked), 'A$1' (row locked), '$A$1' (both locked) — the same
convention spreadsheets use so a copied/filled formula can keep a reference
fixed instead of shifting it. Plain 'A1' means neither is locked.
"""
import re

CELL_RE = re.compile(r"^([A-Za-z]+)(\d+)$")
LOCKED_CELL_RE = re.compile(r"^(\$?)([A-Za-z]+)(\$?)(\d+)$")


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


def parse_ref_locked(ref):
    """Return (col_num, row_num, abs_col, abs_row) for a ref like 'A1', '$A1',
    'A$1', or '$A$1', or raise ValueError."""
    m = LOCKED_CELL_RE.match(ref)
    if not m:
        raise ValueError(f"invalid cell reference: {ref!r}")
    abs_col, letters, abs_row, digits = m.groups()
    return col_to_num(letters), int(digits), bool(abs_col), bool(abs_row)


def parse_ref(ref):
    """Return (col_num, row_num) for a cell reference like 'A1' (optionally
    '$'-locked), or raise ValueError."""
    col, row, _, _ = parse_ref_locked(ref)
    return col, row


def normalize_ref(ref):
    """Canonicalize a cell reference's letter case (A1 == a1), preserving any
    '$' locks."""
    col, row, abs_col, abs_row = parse_ref_locked(ref)
    return f"{'$' if abs_col else ''}{num_to_col(col)}{'$' if abs_row else ''}{row}"


def strip_abs(ref):
    """Drop any '$' locks, returning the plain 'A1'-form reference used as a
    cell's storage key."""
    col, row, _, _ = parse_ref_locked(ref)
    return make_ref(col, row)


def translate_ref(ref, dcol, drow):
    """Shift a (possibly '$'-locked) reference by (dcol, drow), leaving locked
    components unchanged — the core of spreadsheet copy/fill semantics.
    Raises ValueError if the shifted reference would fall off the grid."""
    col, row, abs_col, abs_row = parse_ref_locked(ref)
    new_col = col if abs_col else col + dcol
    new_row = row if abs_row else row + drow
    if new_col < 1 or new_row < 1:
        raise ValueError(f"shifted reference out of bounds: {ref}")
    return f"{'$' if abs_col else ''}{num_to_col(new_col)}{'$' if abs_row else ''}{new_row}"


def make_ref(col_num, row_num):
    return f"{num_to_col(col_num)}{row_num}"


def is_ref(token):
    return bool(LOCKED_CELL_RE.match(token))


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
