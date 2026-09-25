import subprocess
import sys


def test_version():
    result = subprocess.run(
        [sys.executable, "-m", "ttt", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1" in result.stdout
