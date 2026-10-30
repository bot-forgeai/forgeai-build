import os

from searchlite.__main__ import main


def test_add_and_search(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    doc_path = tmp_path / "note.txt"
    doc_path.write_text("the quick brown fox jumps over the lazy dog")

    main(["--index", index_path, "add", str(doc_path)])
    capsys.readouterr()

    main(["--index", index_path, "search", "fox"])
    out = capsys.readouterr().out
    assert "note.txt" in out


def test_search_with_snippet(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    doc_path = tmp_path / "note.txt"
    doc_path.write_text("the quick brown fox jumps over the lazy dog")

    main(["--index", index_path, "add", str(doc_path)])
    capsys.readouterr()

    main(["--index", index_path, "search", "fox", "--snippet"])
    out = capsys.readouterr().out
    assert "**fox**" in out


def test_search_with_bm25_rank(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    doc_path = tmp_path / "note.txt"
    doc_path.write_text("the quick brown fox jumps over the lazy dog")

    main(["--index", index_path, "add", str(doc_path)])
    capsys.readouterr()

    main(["--index", index_path, "search", "fox", "--rank", "bm25"])
    out = capsys.readouterr().out
    assert "note.txt" in out


def test_search_invalid_rank_exits_nonzero(tmp_path):
    index_path = str(tmp_path / "idx.json")
    try:
        main(["--index", index_path, "search", "fox", "--rank", "nope"])
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert exc.code == 2


def test_search_with_phrase_flag(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    doc_a = tmp_path / "a.txt"
    doc_a.write_text("the quick brown fox jumps over the lazy dog")
    doc_b = tmp_path / "b.txt"
    doc_b.write_text("a fox that is quick and brown but never jumps")

    main(["--index", index_path, "add", str(doc_a), str(doc_b)])
    capsys.readouterr()

    main(["--index", index_path, "search", "quick brown fox", "--phrase"])
    out = capsys.readouterr().out
    assert "a.txt" in out
    assert "b.txt" not in out


def test_search_no_results(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    doc = tmp_path / "d.txt"
    doc.write_text("something else")
    main(["--index", index_path, "add", str(doc)])
    capsys.readouterr()
    main(["--index", index_path, "search", "nothing"])
    out = capsys.readouterr().out
    assert "no results" in out


def test_add_dir(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    (tmp_path / "a.txt").write_text("apples and oranges")
    (tmp_path / "b.md").write_text("bananas and grapes")
    (tmp_path / "c.bin").write_text("should be ignored")

    main(["--index", index_path, "add-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert "indexed 2 file(s)" in out


def test_remove(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    doc_path = tmp_path / "note.txt"
    doc_path.write_text("hello world")
    doc_id = os.path.relpath(str(doc_path))

    main(["--index", index_path, "add", str(doc_path)])
    capsys.readouterr()
    main(["--index", index_path, "remove", doc_id])
    out = capsys.readouterr().out
    assert "removed" in out


def test_remove_missing_exits_nonzero(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    doc = tmp_path / "d.txt"
    doc.write_text("something")
    main(["--index", index_path, "add", str(doc)])
    try:
        main(["--index", index_path, "remove", "nope.txt"])
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert exc.code == 1


def test_stats(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    doc_path = tmp_path / "note.txt"
    doc_path.write_text("hello world")
    main(["--index", index_path, "add", str(doc_path)])
    capsys.readouterr()
    main(["--index", index_path, "stats"])
    out = capsys.readouterr().out
    assert "documents: 1" in out


def test_add_missing_file_exits_nonzero(tmp_path):
    index_path = str(tmp_path / "idx.json")
    try:
        main(["--index", index_path, "add", str(tmp_path / "nope.txt")])
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert exc.code == 1


def test_version():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "searchlite", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1" in result.stdout


def test_add_dir_skips_unchanged_and_prunes_deleted(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("alpha text")
    (docs / "b.md").write_text("beta text")
    main(["--index", "i.json", "add-dir", "docs"])
    capsys.readouterr()
    (docs / "b.md").unlink()
    (docs / "a.md").write_text("alpha changed")
    main(["--index", "i.json", "add-dir", "docs"])
    assert "indexed 1 file(s)" in capsys.readouterr().out
    main(["--index", "i.json", "add-dir", "docs"])
    assert "indexed 0 file(s), 1 unchanged" in capsys.readouterr().out
    main(["--index", "i.json", "add-dir", "docs", "--prune"])
    assert "1 pruned" in capsys.readouterr().out
    main(["--index", "i.json", "stats"])
    assert "documents: 1" in capsys.readouterr().out


def test_base_makes_doc_ids_independent_of_cwd(tmp_path, monkeypatch):
    import json
    root = tmp_path / "root"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "a.md").write_text("alpha text")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    main(["--index", "i.json", "--base", str(root), "add-dir", str(root / "notes")])
    assert "notes/a.md" in json.dumps(json.load(open("i.json")))
    main(["--index", "i.json", "--base", str(root), "add-dir", str(root / "notes"), "--prune"])
    main(["--index", "i.json", "stats"])


def test_index_env_var_is_default(tmp_path, monkeypatch, capsys):
    (tmp_path / "a.txt").write_text("alpha text")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SEARCHLITE_INDEX", str(tmp_path / "env.json"))
    main(["add", "a.txt"])
    assert (tmp_path / "env.json").exists()
    assert not (tmp_path / "searchlite.json").exists()


def test_watch_picks_up_changes_between_scans(tmp_path, capsys, monkeypatch):
    import searchlite.__main__ as cli
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("alpha text")
    (docs / "b.md").write_text("beta text")

    def fake_sleep(_seconds):
        # runs between scan 1 and scan 2: add one file, delete another
        (docs / "c.md").write_text("gamma text")
        (docs / "b.md").unlink()

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    main(["--index", "i.json", "watch", "docs", "--max-runs", "2"])
    out = capsys.readouterr().out
    assert "synced: 2 indexed, 0 pruned" in out
    assert "synced: 1 indexed, 1 pruned" in out
    main(["--index", "i.json", "search", "gamma"])
    assert "docs/c.md" in capsys.readouterr().out
    main(["--index", "i.json", "search", "beta"])
    assert "no results" in capsys.readouterr().out


def test_add_lines_indexes_each_line_separately(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    doc_path = tmp_path / "cards.txt"
    doc_path.write_text("apples are red\n\nbananas are yellow\n")

    main(["--index", index_path, "--base", str(tmp_path), "add", "--lines", str(doc_path)])
    capsys.readouterr()

    main(["--index", index_path, "search", "bananas"])
    out = capsys.readouterr().out
    assert "cards.txt:3" in out
    assert "apples" not in out


def test_search_query_without_terms_errors(tmp_path, capsys):
    import pytest

    index_path = str(tmp_path / "idx.json")
    for query in ("", "   ", "the of"):
        with pytest.raises(SystemExit) as exc:
            main(["--index", index_path, "search", query])
        assert exc.value.code == 2
        assert "no searchable terms" in capsys.readouterr().err


def test_search_top_must_be_positive(tmp_path, capsys):
    import pytest

    index_path = str(tmp_path / "idx.json")
    for top in ("0", "-2"):
        with pytest.raises(SystemExit) as exc:
            main(["--index", index_path, "search", "apples", "--top", top])
        assert exc.value.code == 2
        assert "--top must be" in capsys.readouterr().err


def test_watch_does_not_reread_unchanged_files(tmp_path, capsys, monkeypatch):
    import searchlite.__main__ as cli
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("alpha text")
    (docs / "b.md").write_text("beta text")
    reads = []
    real_open = open

    def spy_open(path, *a, **kw):
        if str(path).endswith(".md"):
            reads.append(os.path.basename(str(path)))
        return real_open(path, *a, **kw)

    def fake_sleep(_seconds):
        (docs / "b.md").write_text("beta text changed")

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    monkeypatch.setattr("builtins.open", spy_open)
    main(["--index", "i.json", "watch", "docs", "--max-runs", "2"])
    assert reads == ["a.md", "b.md", "b.md"]  # a.md read once, not on scan 2


def test_watch_reloads_index_rewritten_by_another_process(tmp_path, capsys, monkeypatch):
    import searchlite.__main__ as cli
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("alpha text")
    (tmp_path / "extra.txt").write_text("zebra text")

    def fake_sleep(_seconds):
        main(["--index", "i.json", "add", "extra.txt"])
        (docs / "b.md").write_text("beta text")

    monkeypatch.setattr(cli.time, "sleep", fake_sleep)
    main(["--index", "i.json", "watch", "docs", "--max-runs", "2"])
    capsys.readouterr()
    main(["--index", "i.json", "search", "zebra"])
    assert "extra.txt" in capsys.readouterr().out


def test_corrupt_index_exits_2_with_hint(tmp_path, capsys):
    import pytest
    index_path = tmp_path / "idx.json"
    index_path.write_text('{"postings": {"a": ')  # truncated
    with pytest.raises(SystemExit) as exc:
        main(["--index", str(index_path), "search", "alpha"])
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "corrupt" in err and "--rebuild" in err
    assert index_path.read_text() == '{"postings": {"a": '  # untouched


def test_add_dir_rebuild_sets_corrupt_index_aside(tmp_path, capsys):
    import pytest
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "n.md").write_text("zram swap notes")
    index_path = tmp_path / "idx.json"
    index_path.write_text("not json")
    with pytest.raises(SystemExit):
        main(["--index", str(index_path), "add-dir", str(docs)])
    main(["--index", str(index_path), "--base", str(docs), "add-dir", str(docs), "--rebuild"])
    assert (tmp_path / "idx.json.corrupt").read_text() == "not json"
    capsys.readouterr()
    main(["--index", str(index_path), "search", "zram"])
    assert "n.md" in capsys.readouterr().out


def test_wrong_shape_index_is_corrupt(tmp_path):
    import pytest
    from searchlite.storage import IndexCorruptError, load_index
    p = tmp_path / "i.json"
    p.write_text("[1, 2]")
    with pytest.raises(IndexCorruptError):
        load_index(str(p))


def test_search_json(tmp_path, capsys):
    import json
    index_path = str(tmp_path / "idx.json")
    doc_path = tmp_path / "note.txt"
    doc_path.write_text("the quick brown fox\tjumps over the lazy dog")

    main(["--index", index_path, "add", str(doc_path)])
    capsys.readouterr()

    main(["--index", index_path, "search", "fox", "--json", "--snippet"])
    rows = json.loads(capsys.readouterr().out)
    assert len(rows) == 1
    assert rows[0]["doc_id"].endswith("note.txt")
    assert "**fox**" in rows[0]["preview"]
    assert isinstance(rows[0]["score"], float)

    main(["--index", index_path, "search", "zebra", "--json"])
    assert json.loads(capsys.readouterr().out) == []


def test_read_commands_error_on_missing_index(tmp_path, capsys):
    import pytest
    missing = str(tmp_path / "typo.json")
    for argv in (["search", "alpha"], ["stats"], ["remove", "x.txt"]):
        with pytest.raises(SystemExit) as exc:
            main(["--index", missing] + argv)
        assert exc.value.code == 2
        assert "no index at" in capsys.readouterr().err
    assert not (tmp_path / "typo.json").exists()


def test_similar_command(tmp_path, capsys):
    import pytest
    index_path = str(tmp_path / "idx.json")
    (tmp_path / "a.txt").write_text("zram swap compression memory pressure")
    (tmp_path / "b.txt").write_text("swap memory pressure and zram tuning")
    (tmp_path / "c.txt").write_text("chess openings")
    main(["--index", index_path, "--base", str(tmp_path), "add-dir", str(tmp_path)])
    capsys.readouterr()
    main(["--index", index_path, "similar", "a.txt"])
    out = capsys.readouterr().out
    assert "b.txt" in out and "c.txt" not in out and "a.txt" not in out
    with pytest.raises(SystemExit) as e:
        main(["--index", index_path, "similar", "zzz.txt"])
    assert e.value.code == 1


def test_boost_path_floats_filename_match_to_top(tmp_path, capsys):
    index_path = str(tmp_path / "idx.json")
    a = tmp_path / "misc.txt"
    b = tmp_path / "fox-notes.txt"
    a.write_text("fox fox")
    b.write_text("a fox")
    c = tmp_path / "other.txt"
    c.write_text("dog cat")
    main(["--index", index_path, "add", str(a), str(b), str(c)])
    capsys.readouterr()

    main(["--index", index_path, "search", "fox"])
    plain = capsys.readouterr().out.splitlines()
    assert "misc.txt" in plain[0]

    main(["--index", index_path, "search", "fox", "--boost-path"])
    boosted = capsys.readouterr().out.splitlines()
    assert "fox-notes.txt" in boosted[0]
