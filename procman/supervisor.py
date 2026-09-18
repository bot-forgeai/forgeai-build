"""Process supervision: start, monitor, restart-on-crash, and report status
for a set of child processes described by procman.config.Service."""
import json
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from procman.config import Service


@dataclass
class ProcState:
    service: Service
    proc: Optional[subprocess.Popen] = None
    restarts: int = 0
    last_exit_code: Optional[int] = None
    stopped: bool = False  # deliberately stopped, do not restart

    def status_dict(self) -> dict:
        running = self.proc is not None and self.proc.poll() is None
        return {
            "name": self.service.name,
            "running": running,
            "pid": self.proc.pid if running else None,
            "restarts": self.restarts,
            "last_exit_code": self.last_exit_code,
            "autorestart": self.service.autorestart,
        }


class Supervisor:
    def __init__(self, services: List[Service], log_dir: str, status_path: Optional[str] = None):
        self.services = services
        self.log_dir = log_dir
        self.status_path = status_path
        self.states: Dict[str, ProcState] = {s.name: ProcState(service=s) for s in services}
        os.makedirs(log_dir, exist_ok=True)

    def _log_path(self, name: str) -> str:
        return os.path.join(self.log_dir, f"{name}.log")

    def _spawn(self, state: ProcState):
        svc = state.service
        env = dict(os.environ)
        env.update(svc.env)
        log_file = open(self._log_path(svc.name), "ab")
        state.proc = subprocess.Popen(
            svc.command,
            cwd=svc.cwd,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        state.stopped = False

    def start_all(self):
        for state in self.states.values():
            self._spawn(state)

    def poll_once(self):
        """Check every process once; restart any that crashed and are
        eligible, per autorestart/max_restarts. Returns list of service
        names that were restarted this tick."""
        restarted = []
        for state in self.states.values():
            if state.stopped or state.proc is None:
                continue
            code = state.proc.poll()
            if code is None:
                continue  # still running
            state.last_exit_code = code
            if state.service.autorestart and state.restarts < state.service.max_restarts:
                state.restarts += 1
                self._spawn(state)
                restarted.append(state.service.name)
        if self.status_path:
            self.write_status()
        return restarted

    def stop_all(self, timeout: float = 5.0):
        for state in self.states.values():
            state.stopped = True
            if state.proc is not None and state.proc.poll() is None:
                state.proc.terminate()
        deadline = time.time() + timeout
        for state in self.states.values():
            if state.proc is None:
                continue
            remaining = max(0.0, deadline - time.time())
            try:
                state.proc.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                state.proc.kill()
                state.proc.wait()
        if self.status_path:
            self.write_status()

    def status(self) -> dict:
        return {name: state.status_dict() for name, state in self.states.items()}

    def write_status(self):
        with open(self.status_path + ".tmp", "w") as f:
            json.dump(self.status(), f, indent=2)
        os.replace(self.status_path + ".tmp", self.status_path)

    def run_forever(self, poll_interval: float = 1.0, stop_flag=None, max_iterations=None):
        """Blocking supervise loop. `stop_flag` is an optional callable
        returning True when the loop should exit (used by signal handlers
        and tests); `max_iterations` bounds the loop for deterministic
        tests instead of relying on wall-clock signals."""
        self.start_all()
        if self.status_path:
            self.write_status()
        iterations = 0
        try:
            while True:
                time.sleep(poll_interval)
                self.poll_once()
                iterations += 1
                if stop_flag is not None and stop_flag():
                    break
                if max_iterations is not None and iterations >= max_iterations:
                    break
        finally:
            self.stop_all()
