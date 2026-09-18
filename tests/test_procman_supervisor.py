import json
import sys
import time

from procman.config import Service
from procman.supervisor import Supervisor


def sleep_cmd(seconds):
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


def crash_cmd(code=1):
    return [sys.executable, "-c", f"import sys; sys.exit({code})"]


def wait_until(predicate, timeout=5.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_start_all_spawns_processes(tmp_path):
    services = [Service(name="a", command=sleep_cmd(5))]
    sup = Supervisor(services, log_dir=str(tmp_path / "logs"))
    sup.start_all()
    try:
        assert sup.states["a"].proc.poll() is None
        status = sup.status()
        assert status["a"]["running"] is True
        assert status["a"]["pid"] == sup.states["a"].proc.pid
    finally:
        sup.stop_all()


def test_crashed_process_restarted_when_autorestart(tmp_path):
    services = [Service(name="a", command=crash_cmd(1), autorestart=True, max_restarts=3)]
    sup = Supervisor(services, log_dir=str(tmp_path / "logs"))
    sup.start_all()
    try:
        # first process should exit almost immediately
        assert wait_until(lambda: sup.states["a"].proc.poll() is not None)
        restarted = sup.poll_once()
        assert restarted == ["a"]
        assert sup.states["a"].restarts == 1
        # new process spawned; eventually it crashes too and gets restarted again
        assert wait_until(lambda: sup.states["a"].proc.poll() is not None)
        sup.poll_once()
        assert sup.states["a"].restarts == 2
    finally:
        sup.stop_all()


def test_no_restart_when_autorestart_false(tmp_path):
    services = [Service(name="a", command=crash_cmd(1), autorestart=False)]
    sup = Supervisor(services, log_dir=str(tmp_path / "logs"))
    sup.start_all()
    try:
        assert wait_until(lambda: sup.states["a"].proc.poll() is not None)
        restarted = sup.poll_once()
        assert restarted == []
        assert sup.states["a"].restarts == 0
        assert sup.states["a"].last_exit_code == 1
    finally:
        sup.stop_all()


def test_max_restarts_cap(tmp_path):
    services = [Service(name="a", command=crash_cmd(1), autorestart=True, max_restarts=2)]
    sup = Supervisor(services, log_dir=str(tmp_path / "logs"))
    sup.start_all()
    try:
        for _ in range(5):
            wait_until(lambda: sup.states["a"].proc.poll() is not None)
            sup.poll_once()
        assert sup.states["a"].restarts == 2
        status = sup.status()
        assert status["a"]["running"] is False
    finally:
        sup.stop_all()


def test_stop_all_terminates_running_processes(tmp_path):
    services = [Service(name="a", command=sleep_cmd(30))]
    sup = Supervisor(services, log_dir=str(tmp_path / "logs"))
    sup.start_all()
    pid = sup.states["a"].proc.pid
    sup.stop_all()
    assert sup.states["a"].proc.poll() is not None
    import os
    import errno
    try:
        os.kill(pid, 0)
        alive = True
    except OSError as e:
        alive = e.errno != errno.ESRCH
    assert not alive


def test_write_status_and_status_dict(tmp_path):
    status_path = str(tmp_path / "status.json")
    services = [Service(name="a", command=sleep_cmd(5))]
    sup = Supervisor(services, log_dir=str(tmp_path / "logs"), status_path=status_path)
    sup.start_all()
    try:
        sup.write_status()
        with open(status_path) as f:
            data = json.load(f)
        assert data["a"]["running"] is True
        assert data["a"]["restarts"] == 0
    finally:
        sup.stop_all()


def test_run_forever_with_max_iterations(tmp_path):
    status_path = str(tmp_path / "status.json")
    services = [Service(name="a", command=crash_cmd(1), autorestart=True, max_restarts=5)]
    sup = Supervisor(services, log_dir=str(tmp_path / "logs"), status_path=status_path)
    sup.run_forever(poll_interval=0.1, max_iterations=5)
    # after run_forever returns, all processes must be stopped (stop_all in finally)
    assert sup.states["a"].proc.poll() is not None
    with open(status_path) as f:
        data = json.load(f)
    assert data["a"]["restarts"] >= 1


def test_log_output_captured(tmp_path):
    log_dir = tmp_path / "logs"
    services = [Service(name="a", command=[sys.executable, "-c", "print('hello from a')"])]
    sup = Supervisor(services, log_dir=str(log_dir))
    sup.start_all()
    try:
        wait_until(lambda: sup.states["a"].proc.poll() is not None)
    finally:
        sup.stop_all()
    log_content = (log_dir / "a.log").read_text()
    assert "hello from a" in log_content
