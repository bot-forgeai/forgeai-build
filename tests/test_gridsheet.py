import json

import pytest

from gridsheet import formula
from gridsheet.refs import col_to_num, expand_range, make_ref, normalize_ref, num_to_col, parse_ref
from gridsheet.sheet import Sheet, SheetError
from gridsheet.storage import export_csv, import_csv, load_sheet, save_sheet


# --- refs ---

def test_col_to_num_and_back():
    assert col_to_num("A") == 1
    assert col_to_num("Z") == 26
    assert col_to_num("AA") == 27
    assert col_to_num("AZ") == 52
    assert num_to_col(1) == "A"
    assert num_to_col(26) == "Z"
    assert num_to_col(27) == "AA"


def test_parse_ref():
    assert parse_ref("A1") == (1, 1)
    assert parse_ref("B12") == (2, 12)
    with pytest.raises(ValueError):
        parse_ref("1A")


def test_normalize_ref_case_insensitive():
    assert normalize_ref("a1") == "A1"
    assert normalize_ref("B2") == "B2"


def test_make_ref():
    assert make_ref(1, 1) == "A1"
    assert make_ref(27, 3) == "AA3"


def test_expand_range():
    assert expand_range("A1", "A3") == ["A1", "A2", "A3"]
    assert expand_range("A1", "B2") == ["A1", "B1", "A2", "B2"]
    # order-independent
    assert expand_range("B2", "A1") == ["A1", "B1", "A2", "B2"]


# --- formula parsing/evaluation ---

def lookup_from(values):
    return lambda ref: values.get(ref)


def test_parse_number():
    ast = formula.parse("42")
    assert formula.evaluate(ast, lookup_from({})) == 42.0


def test_parse_arithmetic_precedence():
    ast = formula.parse("2+3*4")
    assert formula.evaluate(ast, lookup_from({})) == 14.0


def test_parse_parens():
    ast = formula.parse("(2+3)*4")
    assert formula.evaluate(ast, lookup_from({})) == 20.0


def test_unary_minus():
    ast = formula.parse("-5+2")
    assert formula.evaluate(ast, lookup_from({})) == -3.0


def test_cell_ref():
    ast = formula.parse("A1+1")
    assert formula.evaluate(ast, lookup_from({"A1": 4.0})) == 5.0


def test_blank_cell_is_zero():
    ast = formula.parse("A1+1")
    assert formula.evaluate(ast, lookup_from({})) == 1.0


def test_division_by_zero():
    ast = formula.parse("1/0")
    with pytest.raises(formula.SheetEvalError, match=r"#DIV/0!"):
        formula.evaluate(ast, lookup_from({}))


def test_sum_function_over_range():
    ast = formula.parse("SUM(A1:A3)")
    values = {"A1": 1.0, "A2": 2.0, "A3": 3.0}
    assert formula.evaluate(ast, lookup_from(values)) == 6.0


def test_avg_min_max_count():
    values = {"A1": 1.0, "A2": 2.0, "A3": 3.0}
    assert formula.evaluate(formula.parse("AVG(A1:A3)"), lookup_from(values)) == 2.0
    assert formula.evaluate(formula.parse("MIN(A1:A3)"), lookup_from(values)) == 1.0
    assert formula.evaluate(formula.parse("MAX(A1:A3)"), lookup_from(values)) == 3.0
    assert formula.evaluate(formula.parse("COUNT(A1:A3)"), lookup_from(values)) == 3.0


def test_function_mixed_args():
    ast = formula.parse("SUM(A1, A2, 10)")
    values = {"A1": 1.0, "A2": 2.0}
    assert formula.evaluate(ast, lookup_from(values)) == 13.0


def test_unknown_function():
    ast = formula.parse("NOPE(A1)")
    with pytest.raises(formula.SheetEvalError, match="#NAME?"):
        formula.evaluate(ast, lookup_from({}))


def test_range_outside_function_is_value_error():
    ast = formula.parse("A1:A3")
    with pytest.raises(formula.SheetEvalError, match="#VALUE!"):
        formula.evaluate(ast, lookup_from({}))


def test_string_in_arithmetic_is_value_error():
    ast = formula.parse("A1+1")
    with pytest.raises(formula.SheetEvalError, match="#VALUE!"):
        formula.evaluate(ast, lookup_from({"A1": "hello"}))


def test_invalid_syntax_raises_formula_error():
    with pytest.raises(formula.FormulaError):
        formula.parse("1+")
    with pytest.raises(formula.FormulaError):
        formula.parse("1 2")


def test_extract_refs_includes_ranges_and_direct_refs():
    ast = formula.parse("A1+SUM(B1:B3)")
    assert formula.extract_refs(ast) == {"A1", "B1", "B2", "B3"}


# --- comparisons ---

@pytest.mark.parametrize(
    "expr,expected",
    [
        ("1=1", 1.0),
        ("1=2", 0.0),
        ("1<>2", 1.0),
        ("1<>1", 0.0),
        ("1<2", 1.0),
        ("2<1", 0.0),
        ("2>1", 1.0),
        ("1>2", 0.0),
        ("2<=2", 1.0),
        ("3<=2", 0.0),
        ("2>=2", 1.0),
        ("2>=3", 0.0),
    ],
)
def test_numeric_comparisons(expr, expected):
    assert formula.evaluate(formula.parse(expr), lookup_from({})) == expected


def test_text_equality_comparison():
    # No string-literal syntax exists in the tokenizer, so text
    # comparisons compare two cell references instead of a literal.
    values = {"A1": "yes", "B1": "yes", "C1": "no"}
    assert formula.evaluate(formula.parse("A1=B1"), lookup_from(values)) == 1.0
    assert formula.evaluate(formula.parse("A1=C1"), lookup_from(values)) == 0.0


def test_comparison_inside_parens_and_arithmetic():
    ast = formula.parse("(1<2)*10")
    assert formula.evaluate(ast, lookup_from({})) == 10.0


# --- IF/ROUND/ABS functions ---

def test_if_true_and_false_branches():
    values = {"A1": 5.0}
    assert formula.evaluate(formula.parse("IF(A1>3, 1, 2)"), lookup_from(values)) == 1.0
    assert formula.evaluate(formula.parse("IF(A1>30, 1, 2)"), lookup_from(values)) == 2.0


def test_if_only_evaluates_taken_branch():
    # The untaken branch divides by zero; IF must not raise for it.
    values = {"A1": 5.0}
    ast = formula.parse("IF(A1>3, 100, 1/0)")
    assert formula.evaluate(ast, lookup_from(values)) == 100.0
    ast2 = formula.parse("IF(A1>30, 1/0, 100)")
    assert formula.evaluate(ast2, lookup_from(values)) == 100.0


def test_if_can_return_text_from_cell_refs():
    # The tokenizer has no string-literal syntax, so a text IF branch
    # has to come from a cell reference rather than a quoted literal.
    text_values = {"A1": 5.0, "B1": "big", "C1": "small"}
    ast = formula.parse("IF(A1>3, B1, C1)")
    assert formula.evaluate(ast, lookup_from(text_values)) == "big"


def test_if_wrong_arg_count_is_value_error():
    ast = formula.parse("IF(1, 2)")
    with pytest.raises(formula.SheetEvalError, match="#VALUE!"):
        formula.evaluate(ast, lookup_from({}))


def test_if_error_condition_propagates():
    ast = formula.parse("IF(1/0, 1, 2)")
    with pytest.raises(formula.SheetEvalError, match=r"#DIV/0!"):
        formula.evaluate(ast, lookup_from({}))


def test_round_function():
    assert formula.evaluate(formula.parse("ROUND(3.14159, 2)"), lookup_from({})) == 3.14
    assert formula.evaluate(formula.parse("ROUND(3.6, 0)"), lookup_from({})) == 4.0


def test_abs_function():
    assert formula.evaluate(formula.parse("ABS(-5)"), lookup_from({})) == 5.0
    assert formula.evaluate(formula.parse("ABS(5)"), lookup_from({})) == 5.0


def test_extract_refs_includes_both_if_branches():
    ast = formula.parse("IF(A1>0, B1, C1)")
    assert formula.extract_refs(ast) == {"A1", "B1", "C1"}


def test_if_in_sheet_recomputes_on_condition_change():
    sheet = Sheet()
    sheet.set_cell("A1", "5")
    sheet.set_cell("B1", '=IF(A1>3, 100, 200)')
    assert sheet.get_value("B1") == 100.0
    sheet.set_cell("A1", "1")
    assert sheet.get_value("B1") == 200.0


# --- Sheet: literals and recomputation ---

def test_set_and_get_numeric_literal():
    sheet = Sheet()
    sheet.set_cell("A1", "5")
    assert sheet.get_value("A1") == 5.0


def test_set_text_literal():
    sheet = Sheet()
    sheet.set_cell("A1", "hello")
    assert sheet.get_value("A1") == "hello"


def test_clear_cell():
    sheet = Sheet()
    sheet.set_cell("A1", "5")
    sheet.set_cell("A1", "")
    assert sheet.get_value("A1") is None


def test_formula_reads_another_cell():
    sheet = Sheet()
    sheet.set_cell("A1", "5")
    sheet.set_cell("B1", "=A1*2")
    assert sheet.get_value("B1") == 10.0


def test_changing_upstream_cell_recomputes_dependents():
    sheet = Sheet()
    sheet.set_cell("A1", "5")
    sheet.set_cell("B1", "=A1*2")
    sheet.set_cell("C1", "=B1+1")
    assert sheet.get_value("C1") == 11.0
    sheet.set_cell("A1", "10")
    assert sheet.get_value("B1") == 20.0
    assert sheet.get_value("C1") == 21.0


def test_forward_reference_before_target_exists():
    sheet = Sheet()
    sheet.set_cell("B1", "=A1+1")
    assert sheet.get_value("B1") == 1.0  # A1 blank -> 0
    sheet.set_cell("A1", "9")
    assert sheet.get_value("B1") == 10.0


def test_sum_range_recomputes_on_any_member_change():
    sheet = Sheet()
    sheet.set_cell("A1", "1")
    sheet.set_cell("A2", "2")
    sheet.set_cell("A3", "3")
    sheet.set_cell("B1", "=SUM(A1:A3)")
    assert sheet.get_value("B1") == 6.0
    sheet.set_cell("A2", "20")
    assert sheet.get_value("B1") == 24.0


def test_direct_self_reference_rejected():
    sheet = Sheet()
    with pytest.raises(SheetError, match="circular"):
        sheet.set_cell("A1", "=A1+1")
    assert sheet.get_value("A1") is None


def test_indirect_cycle_rejected():
    sheet = Sheet()
    sheet.set_cell("A1", "=B1+1")
    with pytest.raises(SheetError, match="circular"):
        sheet.set_cell("B1", "=A1+1")
    # A1's formula is untouched; B1 was never set
    assert sheet.get_value("B1") is None


def test_cycle_rejection_leaves_state_unchanged():
    sheet = Sheet()
    sheet.set_cell("A1", "=B1+1")
    sheet.set_cell("B1", "5")
    assert sheet.get_value("A1") == 6.0
    with pytest.raises(SheetError):
        sheet.set_cell("B1", "=A1+1")
    # B1 should still be its old literal value, not partially rewired
    assert sheet.get_value("B1") == 5.0
    assert sheet.get_value("A1") == 6.0


def test_div_by_zero_propagates_as_error_string():
    sheet = Sheet()
    sheet.set_cell("A1", "0")
    sheet.set_cell("B1", "=1/A1")
    assert sheet.get_value("B1") == "#DIV/0!"


def test_error_propagates_through_dependents():
    sheet = Sheet()
    sheet.set_cell("A1", "0")
    sheet.set_cell("B1", "=1/A1")
    sheet.set_cell("C1", "=B1+1")
    assert sheet.get_value("C1") == "#DIV/0!"
    sheet.set_cell("A1", "2")
    assert sheet.get_value("B1") == 0.5
    assert sheet.get_value("C1") == 1.5


def test_invalid_formula_syntax_rejected_without_mutating():
    sheet = Sheet()
    sheet.set_cell("A1", "5")
    with pytest.raises(SheetError, match="invalid formula"):
        sheet.set_cell("A1", "=1+")
    assert sheet.get_value("A1") == 5.0


def test_bounds():
    sheet = Sheet()
    assert sheet.bounds() == (0, 0)
    sheet.set_cell("C4", "1")
    sheet.set_cell("A1", "2")
    assert sheet.bounds() == (3, 4)


# --- storage ---

def test_save_and_load_round_trip(tmp_path):
    sheet = Sheet()
    sheet.set_cell("A1", "5")
    sheet.set_cell("B1", "=A1*2")
    path = tmp_path / "sheet.json"
    save_sheet(sheet, path)

    loaded = load_sheet(path)
    assert loaded.get_value("A1") == 5.0
    assert loaded.get_value("B1") == 10.0
    assert loaded.get_raw("B1") == "=A1*2"


def test_load_forward_reference_order_independent(tmp_path):
    # B1 references A1 but appears first in the JSON dict.
    path = tmp_path / "sheet.json"
    path.write_text(json.dumps({"B1": "=A1+1", "A1": "9"}))
    loaded = load_sheet(path)
    assert loaded.get_value("B1") == 10.0


def test_load_detects_cycle(tmp_path):
    path = tmp_path / "sheet.json"
    path.write_text(json.dumps({"A1": "=B1+1", "B1": "=A1+1"}))
    with pytest.raises(SheetError, match="circular"):
        load_sheet(path)


def test_load_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        load_sheet("/tmp/does-not-exist-gridsheet-12345.json")


# --- CSV export ---

def test_export_csv_computed_values(tmp_path):
    sheet = Sheet()
    sheet.set_cell("A1", "5")
    sheet.set_cell("B1", "=A1*2")
    sheet.set_cell("A2", "hello")
    csv_path = tmp_path / "out.csv"
    export_csv(sheet, csv_path)
    assert csv_path.read_text() == "5,10\nhello,\n"


def test_export_csv_empty_sheet(tmp_path):
    sheet = Sheet()
    csv_path = tmp_path / "out.csv"
    export_csv(sheet, csv_path)
    assert csv_path.read_text() == ""


def test_export_csv_preserves_float_formatting(tmp_path):
    sheet = Sheet()
    sheet.set_cell("A1", "=1/4")
    csv_path = tmp_path / "out.csv"
    export_csv(sheet, csv_path)
    assert csv_path.read_text() == "0.25\n"


def test_export_csv_error_value(tmp_path):
    sheet = Sheet()
    sheet.set_cell("A1", "=1/0")
    csv_path = tmp_path / "out.csv"
    export_csv(sheet, csv_path)
    assert "#DIV/0!" in csv_path.read_text()


# --- CSV import ---

def test_import_csv_literals(tmp_path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("5,hello\n10,world\n")
    sheet = Sheet()
    import_csv(sheet, csv_path)
    assert sheet.get_value("A1") == 5.0
    assert sheet.get_value("B1") == "hello"
    assert sheet.get_value("A2") == 10.0
    assert sheet.get_value("B2") == "world"


def test_import_csv_formulas(tmp_path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("5,=A1*2\n")
    sheet = Sheet()
    import_csv(sheet, csv_path)
    assert sheet.get_value("B1") == 10.0


def test_import_csv_skips_blank_cells(tmp_path):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("1,,3\n")
    sheet = Sheet()
    import_csv(sheet, csv_path)
    assert sheet.get_value("A1") == 1.0
    assert sheet.get_value("B1") is None
    assert sheet.get_value("C1") == 3.0


def test_import_csv_round_trips_with_export(tmp_path):
    sheet = Sheet()
    sheet.set_cell("A1", "5")
    sheet.set_cell("B1", "=A1*2")
    csv_path = tmp_path / "out.csv"
    export_csv(sheet, csv_path)
    reimported = Sheet()
    import_csv(reimported, csv_path)
    assert reimported.get_value("A1") == 5.0
    assert reimported.get_value("B1") == 10.0


# --- CLI ---

def run_cli(args, capsys):
    from gridsheet.__main__ import main

    code = main(args)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_cli_set_and_get(tmp_path, capsys):
    path = str(tmp_path / "s.json")
    code, _, _ = run_cli(["set", path, "A1", "5"], capsys)
    assert code == 0
    code, _, _ = run_cli(["set", path, "B1", "=A1*2"], capsys)
    assert code == 0
    code, out, _ = run_cli(["get", path, "B1"], capsys)
    assert code == 0
    assert out.strip() == "10"


def test_cli_show(tmp_path, capsys):
    path = str(tmp_path / "s.json")
    run_cli(["set", path, "A1", "1"], capsys)
    run_cli(["set", path, "B1", "2"], capsys)
    code, out, _ = run_cli(["show", path], capsys)
    assert code == 0
    assert "A" in out and "B" in out
    assert "1" in out and "2" in out


def test_cli_show_empty_sheet(tmp_path, capsys):
    path = str(tmp_path / "s.json")
    code, out, _ = run_cli(["show", path], capsys)
    assert code == 0
    assert "empty" in out


def test_cli_set_circular_reference_exits_nonzero(tmp_path, capsys):
    path = str(tmp_path / "s.json")
    code, _, err = run_cli(["set", path, "A1", "=A1+1"], capsys)
    assert code == 1
    assert "circular" in err


def test_cli_get_unset_cell_prints_empty(tmp_path, capsys):
    path = str(tmp_path / "s.json")
    code, out, _ = run_cli(["get", path, "A1"], capsys)
    assert code == 0
    assert out.strip() == ""


def test_cli_import_csv(tmp_path, capsys):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("5,=A1*2\n")
    path = str(tmp_path / "s.json")
    code, _, _ = run_cli(["import", path, str(csv_path)], capsys)
    assert code == 0
    code, out, _ = run_cli(["get", path, "B1"], capsys)
    assert out.strip() == "10"


def test_cli_import_csv_bad_formula_exits_nonzero(tmp_path, capsys):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("=A1+\n")
    path = str(tmp_path / "s.json")
    code, _, err = run_cli(["import", path, str(csv_path)], capsys)
    assert code == 1
    assert "error:" in err


def test_cli_shell_import(tmp_path, capsys, monkeypatch):
    csv_path = tmp_path / "in.csv"
    csv_path.write_text("7\n")
    path = str(tmp_path / "s.json")
    inputs = iter([f"import {csv_path}", "show", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    code, out, _ = run_cli(["shell", path], capsys)
    assert code == 0
    assert "7" in out


def test_cli_shell_set_and_show(tmp_path, capsys, monkeypatch):
    path = str(tmp_path / "s.json")
    inputs = iter(["A1 = 5", "B1 = =A1*2", "show", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    code, out, _ = run_cli(["shell", path], capsys)
    assert code == 0
    assert "10" in out
    loaded = load_sheet(path)
    assert loaded.get_value("B1") == 10.0


def test_cli_shell_get_and_error(tmp_path, capsys, monkeypatch):
    path = str(tmp_path / "s.json")
    inputs = iter(["A1 = 5", "get A1", "A1 = =A1+1", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    code, out, _ = run_cli(["shell", path], capsys)
    assert code == 0
    assert "5" in out
    assert "error:" in out


def test_cli_export(tmp_path, capsys):
    path = str(tmp_path / "s.json")
    csv_path = str(tmp_path / "out.csv")
    run_cli(["set", path, "A1", "1"], capsys)
    run_cli(["set", path, "B1", "=A1+1"], capsys)
    code, _, _ = run_cli(["export", path, csv_path], capsys)
    assert code == 0
    with open(csv_path) as f:
        assert f.read() == "1,2\n"


def test_cli_shell_export(tmp_path, capsys, monkeypatch):
    path = str(tmp_path / "s.json")
    csv_path = str(tmp_path / "out.csv")
    inputs = iter(["A1 = 5", f"export {csv_path}", "quit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    code, out, _ = run_cli(["shell", path], capsys)
    assert code == 0
    assert "exported" in out
    with open(csv_path) as f:
        assert f.read() == "5\n"


# --- absolute/relative refs and fill ---

def test_parse_ref_locked_and_translate_ref():
    from gridsheet.refs import parse_ref_locked, translate_ref

    assert parse_ref_locked("A1") == (1, 1, False, False)
    assert parse_ref_locked("$A1") == (1, 1, True, False)
    assert parse_ref_locked("A$1") == (1, 1, False, True)
    assert parse_ref_locked("$A$1") == (1, 1, True, True)

    assert translate_ref("A1", 1, 2) == "B3"
    assert translate_ref("$A1", 1, 2) == "$A3"
    assert translate_ref("A$1", 1, 2) == "B$1"
    assert translate_ref("$A$1", 1, 2) == "$A$1"
    with pytest.raises(ValueError):
        translate_ref("A1", -1, 0)


def test_strip_abs():
    from gridsheet.refs import strip_abs

    assert strip_abs("A1") == "A1"
    assert strip_abs("$A$1") == "A1"
    assert strip_abs("a$1") == "A1"


def test_normalize_ref_preserves_locks():
    assert normalize_ref("$a$1") == "$A$1"
    assert normalize_ref("a$1") == "A$1"


def test_translate_formula_text():
    assert formula.translate_formula_text("A1+1", 1, 1) == "B2+1"
    assert formula.translate_formula_text("$A1+A$1", 1, 1) == "$A2+B$1"
    assert formula.translate_formula_text("SUM(A1:A3)", 0, 1) == "SUM(A2:A4)"
    with pytest.raises(ValueError):
        formula.translate_formula_text("A1", -1, 0)


def test_formula_with_locked_ref_evaluates_normally():
    sheet = Sheet()
    sheet.set_cell("A1", "10")
    sheet.set_cell("B1", "=$A$1+1")
    assert sheet.get_value("B1") == 11.0


def test_sheet_fill_relative_formula():
    sheet = Sheet()
    sheet.set_cell("A1", "1")
    sheet.set_cell("A2", "2")
    sheet.set_cell("B1", "=A1*10")
    sheet.fill("B1", ["B2"])
    assert sheet.get_raw("B2") == "=A2*10"
    assert sheet.get_value("B2") == 20.0


def test_sheet_fill_locked_ref_stays_fixed():
    sheet = Sheet()
    sheet.set_cell("A1", "3")
    sheet.set_cell("B1", "1")
    sheet.set_cell("B2", "2")
    sheet.set_cell("C1", "=B1*$A$1")
    sheet.fill("C1", ["C2"])
    assert sheet.get_raw("C2") == "=B2*$A$1"
    assert sheet.get_value("C2") == 6.0


def test_sheet_fill_range():
    sheet = Sheet()
    for r in range(1, 4):
        sheet.set_cell(f"A{r}", str(r))
    sheet.set_cell("B1", "=A1*2")
    sheet.fill("B1", ["B2", "B3"])
    assert sheet.get_value("B2") == 4.0
    assert sheet.get_value("B3") == 6.0


def test_sheet_fill_literal_copies_unchanged():
    sheet = Sheet()
    sheet.set_cell("A1", "hello")
    sheet.fill("A1", ["A2"])
    assert sheet.get_value("A2") == "hello"


def test_sheet_fill_out_of_bounds_raises():
    sheet = Sheet()
    sheet.set_cell("B2", "=A1+1")
    with pytest.raises(SheetError):
        sheet.fill("B2", ["A1"])


def test_sheet_fill_skips_self():
    sheet = Sheet()
    sheet.set_cell("A1", "5")
    sheet.fill("A1", ["A1", "A2"])
    assert sheet.get_value("A2") == 5.0


def test_cli_fill(tmp_path, capsys):
    path = str(tmp_path / "s.json")
    run_cli(["set", path, "A1", "1"], capsys)
    run_cli(["set", path, "A2", "2"], capsys)
    run_cli(["set", path, "B1", "=A1*10"], capsys)
    code, _, _ = run_cli(["fill", path, "B1", "B2"], capsys)
    assert code == 0
    code, out, _ = run_cli(["get", path, "B2"], capsys)
    assert out.strip() == "20"


def test_cli_fill_range(tmp_path, capsys):
    path = str(tmp_path / "s.json")
    run_cli(["set", path, "A1", "1"], capsys)
    run_cli(["set", path, "A2", "2"], capsys)
    run_cli(["set", path, "A3", "3"], capsys)
    run_cli(["set", path, "B1", "=A1*10"], capsys)
    code, _, _ = run_cli(["fill", path, "B1", "B2:B3"], capsys)
    assert code == 0
    code, out, _ = run_cli(["get", path, "B3"], capsys)
    assert out.strip() == "30"


def test_cli_fill_out_of_bounds_error(tmp_path, capsys):
    path = str(tmp_path / "s.json")
    run_cli(["set", path, "B2", "=A1+1"], capsys)
    code, _, err = run_cli(["fill", path, "B2", "A1"], capsys)
    assert code == 1
    assert "error" in err


def test_cli_shell_fill(tmp_path, capsys, monkeypatch):
    path = str(tmp_path / "s.json")
    inputs = iter(
        ["A1 = 1", "A2 = 2", "B1 = =A1*10", "fill B1 B2", "get B2", "quit"]
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
    code, out, _ = run_cli(["shell", path], capsys)
    assert code == 0
    assert "20" in out


def test_version():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "gridsheet", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1" in result.stdout
