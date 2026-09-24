"""Bit-level packing/unpacking used by huffc's compressed stream."""


class BitWriter:
    def __init__(self):
        self._bytes = bytearray()
        self._cur = 0
        self._nbits = 0

    def write_bit(self, bit):
        self._cur = (self._cur << 1) | (bit & 1)
        self._nbits += 1
        if self._nbits == 8:
            self._bytes.append(self._cur)
            self._cur = 0
            self._nbits = 0

    def write_bits(self, bitstring):
        for ch in bitstring:
            self.write_bit(1 if ch == "1" else 0)

    def getvalue(self):
        if self._nbits == 0:
            return bytes(self._bytes)
        # Pad the final partial byte with zero bits on the right.
        padded = self._cur << (8 - self._nbits)
        return bytes(self._bytes) + bytes([padded])


class BitReader:
    def __init__(self, data):
        self._data = data
        self._byte_pos = 0
        self._bit_pos = 0  # 0 = most-significant bit of current byte

    def read_bit(self):
        if self._byte_pos >= len(self._data):
            raise EOFError("no more bits to read")
        byte = self._data[self._byte_pos]
        bit = (byte >> (7 - self._bit_pos)) & 1
        self._bit_pos += 1
        if self._bit_pos == 8:
            self._bit_pos = 0
            self._byte_pos += 1
        return bit
