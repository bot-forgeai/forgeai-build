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
