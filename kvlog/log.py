"""Append-only record log: length-prefixed JSON payloads with a CRC32
checksum per record, so a crash mid-write leaves a detectable, truncatable
tail instead of corrupting earlier records.
"""
import json
import struct
import zlib

_LEN_STRUCT = struct.Struct(">I")
_CRC_STRUCT = struct.Struct(">I")


def encode_record(op, key, value=None):
    payload = json.dumps({"op": op, "key": key, "value": value}).encode("utf-8")
    crc = zlib.crc32(payload) & 0xFFFFFFFF
    return _LEN_STRUCT.pack(len(payload)) + payload + _CRC_STRUCT.pack(crc)


def append_record(fileobj, op, key, value=None):
    fileobj.write(encode_record(op, key, value))
    fileobj.flush()


def iter_records(fileobj):
    """Yield (op, key, value) tuples from an open binary file positioned at
    the start of the log. Stops silently at the first incomplete or
    corrupt record, since that's exactly what a crash mid-append leaves
    behind and it should not take down the rest of a valid log.
    """
    while True:
        len_bytes = fileobj.read(_LEN_STRUCT.size)
        if len(len_bytes) < _LEN_STRUCT.size:
            return
        (length,) = _LEN_STRUCT.unpack(len_bytes)
        payload = fileobj.read(length)
        if len(payload) < length:
            return
        crc_bytes = fileobj.read(_CRC_STRUCT.size)
        if len(crc_bytes) < _CRC_STRUCT.size:
            return
        (expected_crc,) = _CRC_STRUCT.unpack(crc_bytes)
        if (zlib.crc32(payload) & 0xFFFFFFFF) != expected_crc:
            return
        try:
            record = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if "op" not in record or "key" not in record:
            return
        yield record["op"], record["key"], record.get("value")
