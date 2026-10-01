"""Pure Raft state machine: a single node's logic, with no I/O of its own.

Driven entirely by two inputs -- tick() and receive(sender, msg) -- and a
propose() call for client commands. Every call returns a list of
(dest_node_id, message_dict) pairs to deliver; the node never performs
network I/O or real-time waiting itself, which makes the whole election/
replication protocol deterministically testable without sockets or clocks.
A transport layer (see transport.py/server.py) is what actually moves these
messages between real processes.
"""
import random

FOLLOWER = "follower"
CANDIDATE = "candidate"
LEADER = "leader"

from raftlite.log import LogEntry, RaftLog


class RaftNode:
    def __init__(self, node_id, peer_ids, election_timeout_range=(10, 20),
                 heartbeat_interval=3, rng=None):
        self.id = node_id
        self.peers = list(peer_ids)
        self.rng = rng if rng is not None else random.Random()
        self.election_timeout_range = election_timeout_range
        self.heartbeat_interval = heartbeat_interval

        self.current_term = 0
        self.voted_for = None
        self.log = RaftLog()
        self.commit_index = 0
        self.last_applied = 0

        self.role = FOLLOWER
        self.leader_id = None
        self.votes_received = set()
        self.next_index = {}
        self.match_index = {}

        self.elapsed = 0
        self.election_timeout = self._random_timeout()
        self.applied_commands = []

    def _random_timeout(self):
        lo, hi = self.election_timeout_range
        return self.rng.randint(lo, hi)

    def _reset_election_timer(self):
        self.elapsed = 0
        self.election_timeout = self._random_timeout()

    def majority(self):
        return (len(self.peers) + 1) // 2 + 1

    # -- periodic clock input -------------------------------------------------

    def tick(self):
        if self.role in (FOLLOWER, CANDIDATE):
            self.elapsed += 1
            if self.elapsed >= self.election_timeout:
                return self._start_election()
            return []
        else:  # LEADER
            self.elapsed += 1
            if self.elapsed >= self.heartbeat_interval:
                self.elapsed = 0
                return self._send_append_entries_all()
            return []

    def _start_election(self):
        self.current_term += 1
        self.role = CANDIDATE
        self.voted_for = self.id
        self.votes_received = {self.id}
        self._reset_election_timer()
        if not self.peers:
            # Single-node cluster: a majority of one is itself.
            return self._become_leader()
        msgs = []
        for p in self.peers:
            msgs.append((p, {
                "type": "RequestVote",
                "term": self.current_term,
                "candidate_id": self.id,
                "last_log_index": self.log.last_index(),
                "last_log_term": self.log.last_term(),
            }))
        return msgs

    def _become_leader(self):
        self.role = LEADER
        self.leader_id = self.id
        self.elapsed = 0
        self.next_index = {p: self.log.last_index() + 1 for p in self.peers}
        self.match_index = {p: 0 for p in self.peers}
        return self._send_append_entries_all()

    def _send_append_entries_all(self):
        return [(p, self._append_entries_msg_for(p)) for p in self.peers]

    def _append_entries_msg_for(self, peer):
        next_idx = self.next_index[peer]
        prev_log_index = next_idx - 1
        prev_log_term = self.log.term_at(prev_log_index)
        entries = [e.to_dict() for e in self.log.slice_from(next_idx)]
        return {
            "type": "AppendEntries",
            "term": self.current_term,
            "leader_id": self.id,
            "prev_log_index": prev_log_index,
            "prev_log_term": prev_log_term,
            "entries": entries,
            "leader_commit": self.commit_index,
        }

    def _step_down_if_stale(self, term):
        if term > self.current_term:
            self.current_term = term
            self.role = FOLLOWER
            self.voted_for = None
            self.leader_id = None
            return True
        return False

    # -- message input ---------------------------------------------------------

    def receive(self, sender, msg):
        mtype = msg["type"]
        if mtype == "RequestVote":
            return self._on_request_vote(sender, msg)
        if mtype == "RequestVoteResponse":
            return self._on_request_vote_response(sender, msg)
        if mtype == "AppendEntries":
            return self._on_append_entries(sender, msg)
        if mtype == "AppendEntriesResponse":
            return self._on_append_entries_response(sender, msg)
        raise ValueError(f"unknown message type: {mtype!r}")

    def _on_request_vote(self, sender, msg):
        self._step_down_if_stale(msg["term"])
        grant = False
        if msg["term"] == self.current_term and self.voted_for in (None, msg["candidate_id"]):
            up_to_date = (
                msg["last_log_term"] > self.log.last_term()
                or (msg["last_log_term"] == self.log.last_term()
                    and msg["last_log_index"] >= self.log.last_index())
            )
            if up_to_date:
                grant = True
                self.voted_for = msg["candidate_id"]
                self._reset_election_timer()
        return [(sender, {"type": "RequestVoteResponse", "term": self.current_term, "vote_granted": grant})]

    def _on_request_vote_response(self, sender, msg):
        if self.role != CANDIDATE:
            return []
        if self._step_down_if_stale(msg["term"]):
            return []
        if msg["term"] != self.current_term or not msg["vote_granted"]:
            return []
        self.votes_received.add(sender)
        if len(self.votes_received) >= self.majority():
            return self._become_leader()
        return []

    def _on_append_entries(self, sender, msg):
        self._step_down_if_stale(msg["term"])
        if msg["term"] < self.current_term:
            return [(sender, {"type": "AppendEntriesResponse", "term": self.current_term,
                               "success": False, "match_index": 0})]

        self.role = FOLLOWER
        self.leader_id = msg["leader_id"]
        self._reset_election_timer()

        prev_index = msg["prev_log_index"]
        prev_term = msg["prev_log_term"]
        if prev_index > 0:
            if prev_index > self.log.last_index() or self.log.term_at(prev_index) != prev_term:
                return [(sender, {"type": "AppendEntriesResponse", "term": self.current_term,
                                   "success": False, "match_index": 0})]

        insert_at = prev_index + 1
        for i, entry_dict in enumerate(msg["entries"]):
            idx = insert_at + i
            entry = LogEntry.from_dict(entry_dict)
            if idx <= self.log.last_index():
                if self.log.term_at(idx) != entry.term:
                    self.log.truncate_from(idx)
                    self.log.append(entry)
            else:
                self.log.append(entry)

        if msg["leader_commit"] > self.commit_index:
            self.commit_index = min(msg["leader_commit"], self.log.last_index())
        self._apply_committed()

        return [(sender, {"type": "AppendEntriesResponse", "term": self.current_term,
                           "success": True, "match_index": prev_index + len(msg["entries"])})]

    def _on_append_entries_response(self, sender, msg):
        if self.role != LEADER:
            return []
        if self._step_down_if_stale(msg["term"]):
            return []
        if msg["term"] != self.current_term:
            return []
        if msg["success"]:
            self.match_index[sender] = msg["match_index"]
            self.next_index[sender] = msg["match_index"] + 1
            self._advance_commit_index()
            self._apply_committed()
            return []
        self.next_index[sender] = max(1, self.next_index[sender] - 1)
        return [(sender, self._append_entries_msg_for(sender))]

    def _advance_commit_index(self):
        for n in range(self.log.last_index(), self.commit_index, -1):
            if self.log.term_at(n) != self.current_term:
                continue
            count = 1
            for p in self.peers:
                if self.match_index.get(p, 0) >= n:
                    count += 1
            if count >= self.majority():
                self.commit_index = n
                break

    def _apply_committed(self):
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log.get(self.last_applied)
            self.applied_commands.append(entry.command)

    # -- client input ------------------------------------------------------------

    def propose(self, command):
        """Append a command to the leader's log. Returns the new log index, or
        None if this node isn't currently the leader."""
        if self.role != LEADER:
            return None
        entry = LogEntry(self.current_term, command)
        self.log.append(entry)
        self.match_index[self.id] = self.log.last_index()
        if not self.peers:
            self._advance_commit_index()
            self._apply_committed()
        return self.log.last_index()
