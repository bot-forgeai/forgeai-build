import os
import random
import subprocess
import sys

import pytest

from huffc.archive import ArchiveError, pack_archive, unpack_archive
from huffc.bitio import BitReader, BitWriter
from huffc.format import FormatError, compress, decompress
from huffc.huffman import build_codes, build_frequencies, build_tree


def test_bitio_round_trip():
    writer = BitWriter()
    bits = "1011001110100011"
    writer.write_bits(bits)
    blob = writer.getvalue()

    reader = BitReader(blob)
    read_back = "".join(str(reader.read_bit()) for _ in range(len(bits)))
    assert read_back == bits


def test_bitio_pads_final_byte_with_zeros():
    writer = BitWriter()
    writer.write_bits("111")
    blob = writer.getvalue()
    assert len(blob) == 1
    assert blob[0] == 0b11100000


def test_build_frequencies():
    assert build_frequencies(b"aab") == {ord("a"): 2, ord("b"): 1}
    assert build_frequencies(b"") == {}


def test_build_tree_single_symbol():
    tree = build_tree({65: 5})
    assert tree.is_leaf()
    assert tree.symbol == 65


def test_build_codes_are_prefix_free():
    freqs = build_frequencies(b"abracadabra")
    tree = build_tree(freqs)
    codes = build_codes(tree)
    # No code is a prefix of another -- required for unambiguous decoding.
    items = list(codes.values())
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            assert not a.startswith(b)
            assert not b.startswith(a)


def test_build_tree_rejects_empty():
    with pytest.raises(ValueError):
        build_tree({})


def test_build_tree_deterministic_regardless_of_dict_order():
    # Same frequencies, different insertion order -- as happens between
    # compress() (first-seen order) and decompress() (sorted header
    # order). Equal-frequency symbols must still merge identically.
    freqs_a = {ord("x"): 2, ord("y"): 2, ord("z"): 1}
    freqs_b = {ord("z"): 1, ord("y"): 2, ord("x"): 2}
    codes_a = build_codes(build_tree(freqs_a))
    codes_b = build_codes(build_tree(freqs_b))
    assert codes_a == codes_b


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"a",
        b"aaaaaaaaaaaa",
        b"the quick brown fox jumps over the lazy dog",
        bytes(range(256)),
        bytes([0, 0, 0, 255, 255, 1, 2, 3] * 50),
    ],
)
def test_compress_decompress_round_trip(data):
    blob = compress(data)
    assert decompress(blob) == data


def test_compress_shrinks_skewed_data():
    data = b"a" * 1000 + b"b" * 10
    blob = compress(data)
    assert len(blob) < len(data)


def test_compress_random_binary_round_trip():
    rng = random.Random(42)
    data = bytes(rng.randrange(256) for _ in range(2000))
    assert decompress(compress(data)) == data


def test_decompress_rejects_bad_magic():
    with pytest.raises(FormatError):
        decompress(b"NOTHUFF...")


def _run_cli(*args, cwd):
    return subprocess.run(
        [sys.executable, "-m", "huffc", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def test_cli_compress_decompress_round_trip(tmp_path):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = tmp_path / "input.txt"
    src.write_text("hello hello hello world\n" * 20)
    comp = tmp_path / "input.huf"
    out = tmp_path / "output.txt"

    r1 = _run_cli("compress", str(src), str(comp), cwd=repo_root)
    assert r1.returncode == 0
    assert "bytes" in r1.stdout

    r2 = _run_cli("decompress", str(comp), str(out), cwd=repo_root)
    assert r2.returncode == 0
    assert out.read_bytes() == src.read_bytes()


def test_cli_stats(tmp_path):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = tmp_path / "input.txt"
    src.write_text("aaaaaaaaaaaaaaaaaaaa")

    r = _run_cli("stats", str(src), cwd=repo_root)
    assert r.returncode == 0
    assert "original:" in r.stdout
    assert "compressed:" in r.stdout


def test_cli_decompress_bad_file_exits_cleanly(tmp_path):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bad = tmp_path / "bad.huf"
    bad.write_bytes(b"not a huffc file")
    out = tmp_path / "out.txt"

    r = _run_cli("decompress", str(bad), str(out), cwd=repo_root)
    assert r.returncode == 1
    assert "error:" in r.stderr


def _run_cli_binary(*args, cwd, input_bytes=b""):
    return subprocess.run(
        [sys.executable, "-m", "huffc", *args],
        cwd=cwd,
        input=input_bytes,
        capture_output=True,
    )


def test_cli_stdin_stdout_round_trip(tmp_path):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    original = b"hello hello hello world\n" * 20

    r1 = _run_cli_binary("compress", "-", "-", cwd=repo_root, input_bytes=original)
    assert r1.returncode == 0
    assert r1.stdout != original

    r2 = _run_cli_binary("decompress", "-", "-", cwd=repo_root, input_bytes=r1.stdout)
    assert r2.returncode == 0
    assert r2.stdout == original


def test_cli_stdin_stdout_no_summary_printed_to_stdout(tmp_path):
    # A summary line on stdout would corrupt a piped binary stream, so it
    # must be suppressed whenever the output side is "-", quiet or not.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = _run_cli_binary("compress", "-", "-", cwd=repo_root, input_bytes=b"aaaa")
    assert r.stderr == b""


def test_cli_stats_from_stdin(tmp_path):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = _run_cli_binary("stats", "-", cwd=repo_root, input_bytes=b"aaaaaaaaaaaaaaaaaaaa")
    assert r.returncode == 0
    assert b"original:" in r.stdout


def test_pack_unpack_archive_round_trip(tmp_path):
    a = tmp_path / "a.txt"
    b = tmp_path / "b.txt"
    a.write_bytes(b"aaaaaaaaaaaaaaaaaaaa")
    b.write_bytes(b"the quick brown fox")

    blob = pack_archive([str(a), str(b)])
    entries = unpack_archive(blob)

    assert [name for name, _ in entries] == ["a.txt", "b.txt"]
    assert entries[0][1] == a.read_bytes()
    assert entries[1][1] == b.read_bytes()


def test_pack_archive_empty_file_list():
    blob = pack_archive([])
    assert unpack_archive(blob) == []


def test_unpack_archive_rejects_bad_magic():
    with pytest.raises(ArchiveError):
        unpack_archive(b"NOTANARCHIVE...")


def test_pack_archive_strips_directory_components(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    f = sub / "nested.txt"
    f.write_bytes(b"hello")

    blob = pack_archive([str(f)])
    entries = unpack_archive(blob)
    assert entries[0][0] == "nested.txt"


def test_cli_archive_extract_round_trip(tmp_path):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    f1 = src_dir / "one.txt"
    f2 = src_dir / "two.txt"
    f1.write_text("hello hello hello\n" * 10)
    f2.write_text("goodbye goodbye\n" * 10)
    archive_path = tmp_path / "bundle.hfa"

    r1 = _run_cli("archive", str(archive_path), str(f1), str(f2), cwd=repo_root)
    assert r1.returncode == 0
    assert "2 file(s)" in r1.stdout

    out_dir = tmp_path / "out"
    r2 = _run_cli("extract", str(archive_path), "-o", str(out_dir), cwd=repo_root)
    assert r2.returncode == 0
    assert (out_dir / "one.txt").read_bytes() == f1.read_bytes()
    assert (out_dir / "two.txt").read_bytes() == f2.read_bytes()


def test_cli_list_archive(tmp_path):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    f = tmp_path / "only.txt"
    f.write_text("some content")
    archive_path = tmp_path / "bundle.hfa"

    _run_cli("archive", str(archive_path), str(f), "-q", cwd=repo_root)
    r = _run_cli("list", str(archive_path), cwd=repo_root)
    assert r.returncode == 0
    assert "only.txt" in r.stdout
    assert "bytes" in r.stdout


def test_cli_extract_bad_archive_exits_cleanly(tmp_path):
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bad = tmp_path / "bad.hfa"
    bad.write_bytes(b"not an archive")

    r = _run_cli("extract", str(bad), cwd=repo_root)
    assert r.returncode == 1
    assert "error:" in r.stderr
