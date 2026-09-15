import subprocess
import sys


def run_play(moves_input, extra_args=()):
    return subprocess.run(
        [sys.executable, "-m", "chesslite", "play", *extra_args],
        input=moves_input,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_two_human_players_foolsmate():
    result = run_play("f2f3\ne7e5\ng2g4\nd8h4\n")
    assert result.returncode == 0
    assert "Checkmate. Black wins." in result.stdout


def test_illegal_move_reprompts_without_crashing():
    result = run_play("e2e5\ne2e4\ne7e5\n")
    assert "error: illegal move" in result.stderr
    assert "White to move" in result.stdout


def test_ai_opponent_plays_black():
    result = run_play("e2e4\n", extra_args=["--ai", "b", "--depth", "1"])
    assert result.returncode == 0
    assert "AI plays" in result.stdout


def test_bad_syntax_reports_clean_error():
    result = run_play("nonsense\ne2e4\n")
    assert "error: unrecognized move syntax" in result.stderr
