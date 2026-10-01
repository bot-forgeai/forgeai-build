"""Wires a RaftNode's pure logic to a real Transport: a ticker thread drives
elections/heartbeats, a lock serializes all access to the node, and committed
commands are applied to an in-memory key-value store that backs client GETs.
"""
import threading
import time

from raftlite.node import RaftNode, LEADER


TICK_INTERVAL = 0.05  # seconds per logical tick


class RaftServer:
    def __init__(self, node_id, bind_address, peer_addresses,
                 election_timeout_range=(10, 20), heartbeat_interval=3, rng=None):
        from raftlite.transport import Transport

        self.node_id = node_id
        self.node = RaftNode(node_id, list(peer_addresses.keys()),
                              election_timeout_range=election_timeout_range,
                              heartbeat_interval=heartbeat_interval, rng=rng)
        self.kv = {}
        self.lock = threading.RLock()
        self.commit_cv = threading.Condition(self.lock)
        self._stop = threading.Event()

        self.transport = Transport(
            node_id, bind_address, peer_addresses,
            on_peer_message=self._on_peer_message,
            on_client_request=self._on_client_request,
        )

    def start(self):
        self.transport.start()
        self._ticker = threading.Thread(target=self._tick_loop, daemon=True)
        self._ticker.start()

    def stop(self):
        self._stop.set()
        self.transport.stop()

    def _dispatch(self, messages):
        for dest, msg in messages:
            self.transport.send(dest, msg)

    def _apply_new_commits(self, before_applied):
        if len(self.node.applied_commands) > before_applied:
            for command in self.node.applied_commands[before_applied:]:
                if command.get("op") == "put":
                    self.kv[command["key"]] = command["value"]
                elif command.get("op") == "delete":
                    self.kv.pop(command["key"], None)
            self.commit_cv.notify_all()

    def _tick_loop(self):
        while not self._stop.is_set():
            time.sleep(TICK_INTERVAL)
            with self.lock:
                before = len(self.node.applied_commands)
                messages = self.node.tick()
                self._apply_new_commits(before)
            self._dispatch(messages)

    def _on_peer_message(self, sender, msg):
        with self.lock:
            before = len(self.node.applied_commands)
            messages = self.node.receive(sender, msg)
            self._apply_new_commits(before)
        self._dispatch(messages)

    def _on_client_request(self, msg):
        op = msg.get("type")
        with self.lock:
            if op == "GET":
                found = msg["key"] in self.kv
                return {"status": "OK", "found": found, "value": self.kv.get(msg["key"])}
            if op == "PUT":
                if self.node.role != LEADER:
                    return {"status": "NOT_LEADER", "leader_id": self.node.leader_id}
                before = len(self.node.applied_commands)
                index = self.node.propose({"op": "put", "key": msg["key"], "value": msg["value"]})
                messages = self.node._send_append_entries_all()
                self._apply_new_commits(before)
            elif op == "DELETE":
                if self.node.role != LEADER:
                    return {"status": "NOT_LEADER", "leader_id": self.node.leader_id}
                before = len(self.node.applied_commands)
                index = self.node.propose({"op": "delete", "key": msg["key"]})
                messages = self.node._send_append_entries_all()
                self._apply_new_commits(before)
            elif op == "STATUS":
                return {"status": "OK", "role": self.node.role, "term": self.node.current_term,
                        "leader_id": self.node.leader_id, "commit_index": self.node.commit_index,
                        "last_applied": self.node.last_applied}
            else:
                return {"status": "ERROR", "message": f"unknown request type {op!r}"}

        self._dispatch(messages)
        committed = self._wait_for_commit(index, timeout=2.0)
        return {"status": "OK" if committed else "TIMEOUT", "index": index}

    def _wait_for_commit(self, index, timeout):
        deadline = time.monotonic() + timeout
        with self.lock:
            while self.node.last_applied < index:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.commit_cv.wait(timeout=remaining)
            return True
