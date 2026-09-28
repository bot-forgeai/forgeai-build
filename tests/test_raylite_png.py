import struct
import zlib

from raylite.png import write_png
from raylite.vec3 import Vec3


def test_write_png_signature_and_ihdr(tmp_path):
    pixels = [[Vec3(1, 0, 0), Vec3(0, 1, 0)], [Vec3(0, 0, 1), Vec3(1, 1, 1)]]
    path = tmp_path / "out.png"
    write_png(str(path), pixels)
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    ihdr_data = data[8 + 8 : 8 + 8 + 13]
    width, height, bit_depth, color_type = struct.unpack(">IIBB", ihdr_data[:10])
    assert (width, height, bit_depth, color_type) == (2, 2, 8, 2)


def test_write_png_pixel_values_round_trip(tmp_path):
    pixels = [[Vec3(1, 0, 0.5)]]
    path = tmp_path / "out.png"
    write_png(str(path), pixels)
    data = path.read_bytes()

    # Locate the IDAT chunk and decompress it to check the raw scanline.
    pos = 8
    idat = b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        chunk_data = data[pos + 8 : pos + 8 + length]
        if tag == b"IDAT":
            idat += chunk_data
        pos += 8 + length + 4

    raw = zlib.decompress(idat)
    assert raw[0] == 0  # filter type: none
    assert raw[1:4] == bytes([255, 0, 128])


def test_write_png_clamps_out_of_range_values(tmp_path):
    pixels = [[Vec3(2.0, -1.0, 0.5)]]
    path = tmp_path / "out.png"
    write_png(str(path), pixels)
    # Should not raise, and should produce a valid, parseable PNG.
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_write_png_empty_grid(tmp_path):
    path = tmp_path / "empty.png"
    write_png(str(path), [])
    data = path.read_bytes()
    ihdr_data = data[8 + 8 : 8 + 8 + 13]
    width, height = struct.unpack(">II", ihdr_data[:8])
    assert (width, height) == (0, 0)


def test_write_png_ends_with_iend(tmp_path):
    pixels = [[Vec3(0, 0, 0)]]
    path = tmp_path / "out.png"
    write_png(str(path), pixels)
    data = path.read_bytes()
    assert data.endswith(b"IEND\xaeB`\x82")
