"""Huffman tree construction and code assignment."""

import heapq
import itertools


class Node:
    __slots__ = ("freq", "symbol", "left", "right")

    def __init__(self, freq, symbol=None, left=None, right=None):
        self.freq = freq
        self.symbol = symbol  # int (0-255) for a leaf, None for an internal node
        self.left = left
        self.right = right

    def is_leaf(self):
        return self.left is None and self.right is None


def build_frequencies(data):
    """Return {byte_value: count} for every distinct byte in data."""
    freqs = {}
    for b in data:
        freqs[b] = freqs.get(b, 0) + 1
    return freqs


def build_tree(freqs):
    """Build a Huffman tree from a {byte_value: count} table.

    Requires at least one symbol. A single-symbol table still produces a
    tree with one leaf, so the caller can assign it the code "0".

    The resulting tree depends only on the frequency values, never on the
    iteration order of the `freqs` dict: ties are broken by symbol value,
    not by insertion order. This matters because the compressor builds
    `freqs` in first-seen-byte order while the decompressor rebuilds it
    from a sorted header -- without a canonical tie-break, equal-frequency
    symbols could merge in a different order on each side, producing two
    differently-shaped (but equally optimal) trees whose codes disagree.
    """
    if not freqs:
        raise ValueError("cannot build a Huffman tree from an empty frequency table")

    counter = itertools.count()  # tie-breaker so heapq never compares Nodes directly
    items = sorted(freqs.items(), key=lambda kv: (kv[1], kv[0]))
    heap = [(freq, next(counter), Node(freq, symbol=sym)) for sym, freq in items]
    heapq.heapify(heap)

    if len(heap) == 1:
        return heap[0][2]

    while len(heap) > 1:
        f1, _, n1 = heapq.heappop(heap)
        f2, _, n2 = heapq.heappop(heap)
        merged = Node(f1 + f2, left=n1, right=n2)
        heapq.heappush(heap, (merged.freq, next(counter), merged))

    return heap[0][2]


def build_codes(root):
    """Return {byte_value: bitstring} by walking the tree."""
    codes = {}
    if root.is_leaf():
        codes[root.symbol] = "0"
        return codes

    stack = [(root, "")]
    while stack:
        node, prefix = stack.pop()
        if node.is_leaf():
            codes[node.symbol] = prefix
            continue
        stack.append((node.left, prefix + "0"))
        stack.append((node.right, prefix + "1"))
    return codes
