import random

from raftlite.node import RaftNode, FOLLOWER, CANDIDATE, LEADER


def make_cluster(n, rng_seed=0, **kwargs):
    ids = list(range(n))
    rngs = [random.Random(rng_seed + i) for i in ids]
    nodes = {i: RaftNode(i, [p for p in ids if p != i], rng=rngs[i], **kwargs) for i in ids}
    return nodes


def deliver(nodes, messages, inbox=None):
    """Deliver a list of (dest, msg) pairs, running receive() on each dest and
    collecting any further outgoing messages. If inbox is given, append there
    instead of recursing immediately (used by run_until_quiet)."""
    out = []
    for dest, msg in messages:
        sender = msg.pop("_sender", None)
        more = nodes[dest].receive(sender, msg)
        out.extend(more)
    return out


def run_round(nodes, pending):
    """Run one delivery round: for each (dest, msg) figure out the sender by
    tagging it when it leaves a node."""
    out = []
    for dest, msg in pending:
        out.extend([])
    return out


def tagged(sender, messages):
    return [(dest, {**msg, "_sender": sender}) for dest, msg in messages]


def run_to_quiescence(nodes, initial, max_rounds=50):
    pending = initial
    for _ in range(max_rounds):
        if not pending:
            return
        next_pending = []
        for dest, msg in pending:
            sender = msg.pop("_sender")
            more = nodes[dest].receive(sender, msg)
            next_pending.extend(tagged(dest, more))
        pending = next_pending
    raise AssertionError("did not reach quiescence")


def elect_leader(nodes, elector_id):
    """Force node `elector_id` to become a candidate and run its election to
    completion, returning the elected leader's id."""
    initial = tagged(elector_id, nodes[elector_id]._start_election())
    run_to_quiescence(nodes, initial)
    leaders = [nid for nid, n in nodes.items() if n.role == LEADER]
    assert len(leaders) == 1, f"expected exactly one leader, got {leaders}"
    return leaders[0]


def test_single_candidate_wins_election():
    nodes = make_cluster(3)
    leader = elect_leader(nodes, 0)
    assert leader == 0
    assert nodes[0].role == LEADER
    assert nodes[1].role == FOLLOWER
    assert nodes[2].role == FOLLOWER
    assert nodes[1].current_term == nodes[0].current_term
    assert nodes[2].voted_for == 0


def test_candidate_does_not_win_without_majority():
    nodes = make_cluster(5)
    # Node 0 starts an election but only node 1 is reachable (2 votes of 5 -- not a majority).
    initial = tagged(0, nodes[0]._start_election())
    reachable = [(dest, msg) for dest, msg in initial if dest == 1]
    run_to_quiescence(nodes, reachable)
    assert nodes[0].role == CANDIDATE
    assert nodes[1].voted_for == 0


def test_single_node_cluster_self_elects():
    nodes = make_cluster(1)
    msgs = nodes[0].tick()
    for _ in range(30):
        if nodes[0].role == LEADER:
            break
        msgs = nodes[0].tick()
    assert nodes[0].role == LEADER


def test_log_replication_commits_on_majority():
    nodes = make_cluster(3)
    leader_id = elect_leader(nodes, 0)
    leader = nodes[leader_id]
    idx = leader.propose({"op": "put", "key": "x", "value": "1"})
    assert idx == 1
    assert leader.commit_index == 0  # not yet replicated

    initial = tagged(leader_id, leader._send_append_entries_all())
    run_to_quiescence(nodes, initial)

    assert leader.commit_index == 1
    assert leader.applied_commands == [{"op": "put", "key": "x", "value": "1"}]
    # Followers only learn the new commit index on the *next* heartbeat
    # (the first round's AppendEntries carried the leader's pre-commit
    # leader_commit value), matching the real Raft protocol.
    initial = tagged(leader_id, leader._send_append_entries_all())
    run_to_quiescence(nodes, initial)
    for nid, n in nodes.items():
        if nid == leader_id:
            continue
        assert n.log.last_index() == 1
        assert n.commit_index == 1
        assert n.applied_commands == [{"op": "put", "key": "x", "value": "1"}]


def test_non_leader_cannot_propose():
    nodes = make_cluster(3)
    assert nodes[1].propose({"op": "noop"}) is None


def test_higher_term_append_entries_demotes_leader():
    nodes = make_cluster(3)
    leader_id = elect_leader(nodes, 0)
    other = [n for n in nodes if n != leader_id][0]

    # Simulate a newer leader (higher term) sending AppendEntries to the old leader.
    msg = {"type": "AppendEntries", "term": nodes[leader_id].current_term + 5,
           "leader_id": other, "prev_log_index": 0, "prev_log_term": 0,
           "entries": [], "leader_commit": 0}
    nodes[leader_id].receive(other, msg)
    assert nodes[leader_id].role == FOLLOWER
    assert nodes[leader_id].current_term == msg["term"]
    assert nodes[leader_id].leader_id == other


def test_follower_log_conflict_is_truncated():
    nodes = make_cluster(3)
    leader_id = elect_leader(nodes, 0)
    leader = nodes[leader_id]
    follower_id = [n for n in nodes if n != leader_id][0]
    follower = nodes[follower_id]

    # Give the follower a bogus conflicting entry at index 1, term 1 higher than reality.
    from raftlite.log import LogEntry
    follower.log.append(LogEntry(term=leader.current_term + 1, command="bogus"))

    leader.propose({"op": "put", "key": "a", "value": "1"})
    initial = tagged(leader_id, leader._send_append_entries_all())
    run_to_quiescence(nodes, initial)

    assert follower.log.get(1).command == {"op": "put", "key": "a", "value": "1"}


def test_tick_triggers_election_after_timeout():
    nodes = make_cluster(3, election_timeout_range=(3, 3))
    pending = []
    for _ in range(3):
        pending = tagged(0, nodes[0].tick())
    assert nodes[0].role == CANDIDATE
    assert pending  # RequestVote messages were produced


def test_leader_sends_heartbeats_on_interval():
    nodes = make_cluster(3)
    leader_id = elect_leader(nodes, 0)
    leader = nodes[leader_id]
    leader.elapsed = 0
    msgs = []
    for _ in range(leader.heartbeat_interval):
        msgs = leader.tick()
    assert len(msgs) == len(leader.peers)
    assert all(m["type"] == "AppendEntries" for _, m in msgs)


def test_multiple_commands_apply_in_order():
    nodes = make_cluster(3)
    leader_id = elect_leader(nodes, 0)
    leader = nodes[leader_id]
    for i in range(3):
        leader.propose({"op": "put", "key": str(i), "value": i})
        initial = tagged(leader_id, leader._send_append_entries_all())
        run_to_quiescence(nodes, initial)
        # One extra heartbeat round so followers learn of the commit advance
        # before the next propose, keeping leader and followers in sync.
        initial = tagged(leader_id, leader._send_append_entries_all())
        run_to_quiescence(nodes, initial)
    assert leader.applied_commands == [
        {"op": "put", "key": "0", "value": 0},
        {"op": "put", "key": "1", "value": 1},
        {"op": "put", "key": "2", "value": 2},
    ]
    for nid, n in nodes.items():
        assert n.applied_commands == leader.applied_commands
