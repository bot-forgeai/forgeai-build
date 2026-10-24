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
