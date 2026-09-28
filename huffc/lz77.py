"""A small LZ77/LZSS pre-pass for huffc.

Plain Huffman coding only weights individual byte *frequencies*, so it
can't exploit repeated multi-byte runs or substrings (e.g. the same word
appearing many times, or long stretches of whitespace) -- every
occurrence of a byte costs the same number of bits regardless of what
came before it. This module replaces repeated substrings with short
back-references before the data ever reaches the Huffman coder, so
those repeats collapse to a handful of bytes instead of being re-coded
in full each time. The output is still just a byte string, so it feeds
straight into the *existing* frequency/tree/code machinery in
huffman.py -- no changes needed there.

Encoding: a byte-oriented LZSS scheme.

- A literal byte is emitted as-is, *unless* it equals the ESCAPE byte
  (0xFF), in which case it's escaped as ESCAPE, ESCAPE -- a doubled
  escape byte can never be mistaken for the start of a match, since
  WINDOW_SIZE (4096) keeps a match's distance high byte well below
  0xFF (max high byte is 0x10).
- A match is emitted as ESCAPE, distance (2 bytes, big-endian, 1-based:
  1 means "the immediately preceding byte"), length (1 byte, the match
  length minus MIN_MATCH plus 1, so it's never 0 and covers lengths
  MIN_MATCH..MIN_MATCH+254).

Matches are found by a naive scan over a bounded sliding window
(WINDOW_SIZE). This is O(window * length) rather than a hash-chain
index, which is simpler and plenty fast enough for the file sizes this
project targets on a Raspberry Pi, but would need revisiting for much
larger inputs.
"""

ESCAPE = 0xFF
WINDOW_SIZE = 4096
MIN_MATCH = 3
MAX_MATCH = 255 + MIN_MATCH - 1  # length byte range is 1..255


def _find_match(data, pos, window_start):
    """Return (distance, length) for the longest match ending before `pos`,
    or (0, 0) if no match of at least MIN_MATCH is found."""
    best_len = 0
    best_dist = 0
    limit = min(len(data), pos + MAX_MATCH)
    for start in range(window_start, pos):
        length = 0
        while pos + length < limit and data[start + length] == data[pos + length]:
            length += 1
        if length > best_len:
            best_len = length
            best_dist = pos - start
    if best_len >= MIN_MATCH:
        return best_dist, best_len
    return 0, 0


def lz77_compress(data):
    out = bytearray()
    pos = 0
    n = len(data)
    while pos < n:
        window_start = max(0, pos - WINDOW_SIZE)
        dist, length = _find_match(data, pos, window_start)
        if length >= MIN_MATCH:
            out.append(ESCAPE)
            out += dist.to_bytes(2, "big")
            out.append(length - MIN_MATCH + 1)
            pos += length
        else:
            b = data[pos]
            out.append(b)
            if b == ESCAPE:
                out.append(ESCAPE)
            pos += 1
    return bytes(out)


def lz77_decompress(encoded):
    out = bytearray()
    pos = 0
    n = len(encoded)
    while pos < n:
        b = encoded[pos]
        if b == ESCAPE:
            marker = encoded[pos + 1]
            if marker == ESCAPE:
                out.append(ESCAPE)
                pos += 2
                continue
            dist = int.from_bytes(encoded[pos + 1 : pos + 3], "big")
            length = encoded[pos + 3] + MIN_MATCH - 1
            pos += 4
            start = len(out) - dist
            for i in range(length):
                out.append(out[start + i])
        else:
            out.append(b)
            pos += 1
    return bytes(out)
