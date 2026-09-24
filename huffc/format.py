"""Container format for huffc's compressed files.

Layout:
    magic (5 bytes)      b"HUFC1"
    num_symbols (2 bytes, big-endian)   0-256
    per symbol (5 bytes each): byte value (1) + frequency (4, big-endian)
    bitstream (remaining bytes, zero-padded to a whole byte)

The frequency table lets the decoder rebuild the exact same Huffman tree
used to encode, and the sum of frequencies tells it exactly how many
symbols to decode -- so no separate padding-length field is needed.
"""

import struct

from .bitio import BitReader, BitWriter
from .huffman import build_codes, build_frequencies, build_tree

MAGIC = b"HUFC1"


class FormatError(Exception):
    pass


def compress(data):
    freqs = build_frequencies(data)

    header = bytearray(MAGIC)
    header += struct.pack(">H", len(freqs))
    for sym, freq in sorted(freqs.items()):
        header += struct.pack(">BI", sym, freq)

    if not freqs:
        return bytes(header)

    tree = build_tree(freqs)
    codes = build_codes(tree)

    writer = BitWriter()
    for b in data:
        writer.write_bits(codes[b])

    return bytes(header) + writer.getvalue()


def decompress(blob):
    if blob[:5] != MAGIC:
        raise FormatError("not a huffc file (bad magic)")

    pos = 5
    (num_symbols,) = struct.unpack_from(">H", blob, pos)
    pos += 2

    freqs = {}
    for _ in range(num_symbols):
        sym, freq = struct.unpack_from(">BI", blob, pos)
        pos += 5
        freqs[sym] = freq

    if not freqs:
        return b""

    total = sum(freqs.values())
    tree = build_tree(freqs)

    out = bytearray()
    reader = BitReader(blob[pos:])
    node = tree
    while len(out) < total:
        if node.is_leaf():
            out.append(node.symbol)
            node = tree
            if len(out) == total:
                break
            continue
        bit = reader.read_bit()
        node = node.right if bit else node.left

    return bytes(out)
