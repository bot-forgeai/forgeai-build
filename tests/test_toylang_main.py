from toylang.__main__ import main


def write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content)
    return str(path)


def test_run_script_success(tmp_path, capsys):
    path = write(tmp_path, "prog.tl", 'print("hello");')
    assert main([path]) == 0
    assert capsys.readouterr().out == "hello\n"


def test_run_script_runtime_error_exits_nonzero(tmp_path, capsys):
    path = write(tmp_path, "bad.tl", "print(missing);")
    assert main([path]) == 1
    assert "error:" in capsys.readouterr().err


def test_run_script_syntax_error_exits_nonzero(tmp_path, capsys):
    path = write(tmp_path, "bad.tl", "let x = ;")
    assert main([path]) == 1
    assert "error:" in capsys.readouterr().err


def test_run_bundled_sample(capsys):
    import toylang
    import os
    sample_path = os.path.join(os.path.dirname(toylang.__file__), "sample.tl")
    assert main([sample_path]) == 0
    out = capsys.readouterr().out
    assert "fib(7) = 13" in out
    assert "counter: 1 2 3" in out


def test_repl_evaluates_lines_without_trailing_semicolon(monkeypatch, capsys):
    inputs = iter(['let x = 1', 'print(x + 1)', ''])

    def fake_input(prompt):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "2" in out


def test_repl_reports_error_and_continues(monkeypatch, capsys):
    inputs = iter(['print(missing)', 'print(1)'])

    def fake_input(prompt):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    assert main([]) == 0
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "1" in captured.out


def test_repl_accepts_multiline_block(monkeypatch, capsys):
    inputs = iter([
        'func greet(name) {',
        '  print("hi " + name);',
        '}',
        'greet("ada");',
    ])

    def fake_input(prompt):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    assert main([]) == 0
    assert "hi ada\n" in capsys.readouterr().out


def test_repl_shows_continuation_prompt_for_open_block(monkeypatch, capsys):
    prompts = []
    inputs = iter(['while (false) {', 'print(1);', '}'])

    def fake_input(prompt):
        prompts.append(prompt)
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    assert main([]) == 0
    assert prompts == ["> ", "... ", "... ", "> "]


def test_repl_accepts_multiline_string_literal(monkeypatch, capsys):
    inputs = iter(['print("line one', 'line two")'])

    def fake_input(prompt):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    assert main([]) == 0
    assert "line one\nline two\n" in capsys.readouterr().out


def test_version():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "toylang", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1" in result.stdout
