from raylite.ppm import write_ppm
from raylite.vec3 import Vec3


def test_write_ppm_header_and_size(tmp_path):
    pixels = [[Vec3(1, 0, 0), Vec3(0, 1, 0)], [Vec3(0, 0, 1), Vec3(1, 1, 1)]]
    path = tmp_path / "out.ppm"
    write_ppm(str(path), pixels)
    data = path.read_bytes()
    assert data.startswith(b"P6\n2 2\n255\n")


def test_write_ppm_pixel_values(tmp_path):
    pixels = [[Vec3(1, 0, 0.5)]]
    path = tmp_path / "out.ppm"
    write_ppm(str(path), pixels)
    data = path.read_bytes()
    header_end = data.index(b"255\n") + 4
    body = data[header_end:]
    assert body == bytes([255, 0, 128])


def test_write_ppm_empty_grid(tmp_path):
    path = tmp_path / "empty.ppm"
    write_ppm(str(path), [])
    data = path.read_bytes()
    assert data == b"P6\n0 0\n255\n"
