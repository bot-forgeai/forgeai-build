import io

from kvlog.log import append_record, encode_record, iter_records


def test_encode_decode_roundtrip():
    buf = io.BytesIO()
    append_record(buf, "put", "a", "1")
    append_record(buf, "put", "b", {"nested": True})
    append_record(buf, "delete", "a")
    buf.seek(0)
    records = list(iter_records(buf))
    assert records == [
        ("put", "a", "1"),
        ("put", "b", {"nested": True}),
        ("delete", "a", None),
    ]


def test_truncated_tail_is_dropped_not_raised():
    buf = io.BytesIO()
    append_record(buf, "put", "a", "1")
    good = buf.getvalue()
    record2 = encode_record("put", "b", "2")
    # simulate a crash mid-write: only part of the second record's bytes
    # made it to disk
    truncated = good + record2[: len(record2) // 2]
    records = list(iter_records(io.BytesIO(truncated)))
    assert records == [("put", "a", "1")]


def test_corrupt_checksum_stops_replay():
    buf = io.BytesIO()
    append_record(buf, "put", "a", "1")
    record2 = bytearray(encode_record("put", "b", "2"))
    record2[-1] ^= 0xFF  # flip a bit in the checksum
    data = buf.getvalue() + bytes(record2)
    records = list(iter_records(io.BytesIO(data)))
    assert records == [("put", "a", "1")]


def test_empty_log():
    assert list(iter_records(io.BytesIO(b""))) == []
