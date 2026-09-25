from shortlink.__main__ import build_arg_parser, get_lan_ip


def test_default_host_is_localhost():
    args = build_arg_parser().parse_args([])
    assert args.host == "127.0.0.1"


def test_host_flag_accepts_any_address():
    args = build_arg_parser().parse_args(["--host", "0.0.0.0"])
    assert args.host == "0.0.0.0"


def test_get_lan_ip_returns_a_dotted_quad():
    ip = get_lan_ip()
    parts = ip.split(".")
    assert len(parts) == 4
    assert all(part.isdigit() for part in parts)


def test_version():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "shortlink", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1" in result.stdout
