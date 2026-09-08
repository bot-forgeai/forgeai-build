import pytest

from shortlink import db


def _conn(tmp_path):
    return db.connect(str(tmp_path / "test.db"))


def test_create_link_generates_a_code(tmp_path):
    conn = _conn(tmp_path)
    code = db.create_link(conn, "https://example.com")
    assert code
    assert db.get_link(conn, code) == "https://example.com"


def test_create_link_with_explicit_code(tmp_path):
    conn = _conn(tmp_path)
    code = db.create_link(conn, "https://example.com", code="mine")
    assert code == "mine"
    assert db.get_link(conn, "mine") == "https://example.com"


def test_create_link_rejects_duplicate_explicit_code(tmp_path):
    conn = _conn(tmp_path)
    db.create_link(conn, "https://example.com", code="mine")
    with pytest.raises(ValueError):
        db.create_link(conn, "https://other.com", code="mine")


def test_get_link_missing_code_returns_none(tmp_path):
    conn = _conn(tmp_path)
    assert db.get_link(conn, "nope") is None


def test_record_click_and_stats(tmp_path):
    conn = _conn(tmp_path)
    code = db.create_link(conn, "https://example.com")
    assert db.get_stats(conn, code)["clicks"] == 0
    db.record_click(conn, code)
    db.record_click(conn, code)
    stats = db.get_stats(conn, code)
    assert stats["clicks"] == 2
    assert stats["url"] == "https://example.com"
    assert stats["last_clicked_at"] is not None


def test_get_stats_missing_code_returns_none(tmp_path):
    conn = _conn(tmp_path)
    assert db.get_stats(conn, "nope") is None


def test_list_links_newest_first_with_click_counts(tmp_path):
    conn = _conn(tmp_path)
    first = db.create_link(conn, "https://a.example.com")
    second = db.create_link(conn, "https://b.example.com")
    db.record_click(conn, first)
    links = db.list_links(conn)
    assert [l["code"] for l in links] == [second, first]
    by_code = {l["code"]: l for l in links}
    assert by_code[first]["clicks"] == 1
    assert by_code[second]["clicks"] == 0
