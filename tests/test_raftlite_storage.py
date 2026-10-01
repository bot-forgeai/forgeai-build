import os

from raftlite.node import LogEntry
from raftlite import storage


def test_load_state_missing_file_returns_none(tmp_path):
    assert storage.load_state(str(tmp_path / "nope.json")) is None


def test_save_then_load_round_trip(tmp_path):
    path = str(tmp_path / "state.json")
    entries = [LogEntry(1, {"op": "put", "key": "a", "value": 1}),
               LogEntry(1, {"op": "put", "key": "b", "value": 2}),
               LogEntry(2, {"op": "delete", "key": "a"})]
    storage.save_state(path, current_term=2, voted_for=3, log_entries=entries)

    term, voted_for, loaded = storage.load_state(path)
    assert term == 2
    assert voted_for == 3
    assert loaded == entries


def test_save_overwrites_previous_state(tmp_path):
    path = str(tmp_path / "state.json")
    storage.save_state(path, 1, None, [LogEntry(1, {"op": "put", "key": "x", "value": 1})])
    storage.save_state(path, 5, 2, [])

    term, voted_for, loaded = storage.load_state(path)
    assert term == 5
    assert voted_for == 2
    assert loaded == []


def test_save_leaves_no_leftover_temp_file(tmp_path):
    path = str(tmp_path / "state.json")
    storage.save_state(path, 1, None, [])
    assert os.path.exists(path)
    assert not os.path.exists(path + ".tmp")


def test_voted_for_none_round_trips(tmp_path):
    path = str(tmp_path / "state.json")
    storage.save_state(path, 0, None, [])
    term, voted_for, loaded = storage.load_state(path)
    assert term == 0
    assert voted_for is None
    assert loaded == []
