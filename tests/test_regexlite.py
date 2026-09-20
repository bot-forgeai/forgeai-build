import subprocess
import sys

import pytest

from regexlite.matcher import Pattern, findall, fullmatch, match, search
from regexlite.parser import RegexSyntaxError, parse


# ---- parser -----------------------------------------------------------

def test_parse_literal():
    ast = parse("abc")
    assert repr(ast) == "Concat([Char('a'), Char('b'), Char('c')])"


def test_parse_alt():
    ast = parse("a|b")
    assert repr(ast) == "Alt([Char('a'), Char('b')])"


def test_parse_repeat_ops():
    assert repr(parse("a*")) == "Star(Char('a'))"
    assert repr(parse("a+")) == "Plus(Char('a'))"
    assert repr(parse("a?")) == "Quest(Char('a'))"


def test_parse_group():
    ast = parse("(ab)+")
    assert repr(ast) == "Plus(Group(Concat([Char('a'), Char('b')]), index=1))"


def test_parse_charclass_range():
    ast = parse("[a-c]")
    assert ast.ranges == [(ord("a"), ord("c"))]
    assert not ast.negate


def test_parse_charclass_negated():
    ast = parse("[^a-c]")
    assert ast.negate


def test_parse_shorthand_digit():
    ast = parse(r"\d")
    assert ast.ranges == [(ord("0"), ord("9"))]


def test_parse_shorthand_negated_digit():
    ast = parse(r"\D")
    assert ast.negate


def test_parse_unbalanced_paren_raises():
    with pytest.raises(RegexSyntaxError):
        parse("(ab")


def test_parse_dangling_escape_raises():
    with pytest.raises(RegexSyntaxError):
        parse("a\\")


def test_parse_empty_charclass_raises():
    with pytest.raises(RegexSyntaxError):
        parse("[]")


def test_parse_unterminated_charclass_raises():
    with pytest.raises(RegexSyntaxError):
        parse("[abc")


def test_parse_stray_metachar_raises():
    with pytest.raises(RegexSyntaxError):
        parse("*abc")


def test_parse_bound_exact():
    assert repr(parse("a{3}")) == "Concat([Char('a'), Char('a'), Char('a')])"


def test_parse_bound_range():
    ast = parse("a{2,4}")
    assert repr(ast) == (
        "Concat([Char('a'), Char('a'), Quest(Char('a')), Quest(Char('a'))])"
    )


def test_parse_bound_unbounded():
    ast = parse("a{2,}")
    assert repr(ast) == "Concat([Char('a'), Char('a'), Star(Char('a'))])"


def test_parse_bound_zero_exact_matches_empty():
    assert repr(parse("a{0}")) == "Concat([])"


def test_parse_bound_invalid_range_raises():
    with pytest.raises(RegexSyntaxError):
        parse("a{4,2}")


def test_parse_bound_too_large_raises():
    with pytest.raises(RegexSyntaxError):
        parse("a{5000}")


def test_parse_unmatched_brace_is_literal():
    # '{' not followed by a valid bound falls back to a literal char,
    # same tolerant style as the rest of the parser.
    assert repr(parse("a{")) == "Concat([Char('a'), Char('{')])"


# ---- matcher: match/fullmatch ------------------------------------------

def test_match_literal():
    m = match("abc", "abcdef")
    assert m is not None
    assert m.group() == "abc"
    assert m.span() == (0, 3)


def test_match_requires_start_anchor_but_not_full():
    assert match("abc", "abXYZ") is None
    assert match("ab", "abXYZ").group() == "ab"


def test_fullmatch_requires_whole_string():
    assert fullmatch("ab", "abXYZ") is None
    assert fullmatch("ab", "ab").group() == "ab"


def test_star_matches_zero_or_more():
    assert fullmatch("a*", "").group() == ""
    assert fullmatch("a*", "aaaa").group() == "aaaa"


def test_plus_requires_at_least_one():
    assert fullmatch("a+", "") is None
    assert fullmatch("a+", "aaa").group() == "aaa"


def test_quest_optional():
    assert fullmatch("ab?c", "ac").group() == "ac"
    assert fullmatch("ab?c", "abc").group() == "abc"


def test_alternation():
    assert fullmatch("cat|dog", "cat") is not None
    assert fullmatch("cat|dog", "dog") is not None
    assert fullmatch("cat|dog", "bird") is None


def test_dot_matches_any_char():
    assert fullmatch("a.c", "abc") is not None
    assert fullmatch("a.c", "axc") is not None
    assert fullmatch("a.c", "ac") is None


def test_grouping_with_repetition():
    assert fullmatch("(ab)+", "ababab") is not None
    assert fullmatch("(ab)+", "aba") is None


def test_bound_exact_count():
    assert fullmatch("a{3}", "aaa") is not None
    assert fullmatch("a{3}", "aa") is None
    assert fullmatch("a{3}", "aaaa") is None


def test_bound_range():
    assert fullmatch("a{2,4}", "a") is None
    assert fullmatch("a{2,4}", "aa") is not None
    assert fullmatch("a{2,4}", "aaaa") is not None
    assert fullmatch("a{2,4}", "aaaaa") is None


def test_bound_unbounded_minimum():
    assert fullmatch("a{2,}", "a") is None
    assert fullmatch("a{2,}", "aa") is not None
    assert fullmatch("a{2,}", "aaaaaaaa") is not None


def test_bound_zero_exact_matches_empty_only():
    assert fullmatch("a{0}", "") is not None
    assert fullmatch("a{0}", "a") is None


def test_bound_on_group():
    assert fullmatch("(ab){2,3}", "abab") is not None
    assert fullmatch("(ab){2,3}", "ababab") is not None
    assert fullmatch("(ab){2,3}", "ab") is None
    assert fullmatch("(ab){2,3}", "abababab") is None


def test_charclass_matching():
    assert fullmatch("[a-c]+", "abcabc") is not None
    assert fullmatch("[a-c]+", "abcd") is None


def test_negated_charclass():
    assert fullmatch("[^0-9]+", "abc") is not None
    assert fullmatch("[^0-9]+", "ab1") is None


def test_digit_shorthand():
    assert fullmatch(r"\d+", "12345") is not None
    assert fullmatch(r"\d+", "12a45") is None


def test_word_shorthand():
    assert fullmatch(r"\w+", "abc_123") is not None
    assert fullmatch(r"\w+", "abc-123") is None


def test_anchors_start_end():
    assert search("^abc$", "abc") is not None
    assert search("^abc$", "xabc") is None
    assert search("^abc$", "abcx") is None


def test_greedy_star_matches_longest():
    m = match("a*", "aaabbb")
    assert m.group() == "aaa"


# ---- matcher: capturing groups ------------------------------------------

def test_group_basic_capture():
    m = fullmatch(r"(\w+)@(\w+)", "alice@example")
    assert m.group(1) == "alice"
    assert m.group(2) == "example"
    assert m.group(0) == "alice@example"
    assert m.groups() == ("alice", "example")


def test_group_span():
    m = fullmatch(r"a(bc)d", "abcd")
    assert m.span(1) == (1, 3)
    assert m.start(1) == 1
    assert m.end(1) == 3


def test_group_no_captures_when_pattern_has_none():
    m = fullmatch("abc", "abc")
    assert m.groups() == ()


def test_group_unmatched_alternative_branch_is_none():
    m = fullmatch(r"(a)|(b)", "b")
    assert m.group(1) is None
    assert m.group(2) == "b"


def test_group_inside_quest_not_taken_is_none():
    m = fullmatch(r"a(b)?", "a")
    assert m.group(1) is None


def test_group_nested():
    m = fullmatch(r"((a)(b))", "ab")
    assert m.group(1) == "ab"
    assert m.group(2) == "a"
    assert m.group(3) == "b"


def test_group_repeated_in_star_keeps_last_iteration():
    # Python's re has the same behavior: a capturing group inside a
    # repetition only remembers its last iteration's span.
    m = fullmatch(r"(a)+", "aaa")
    assert m.group(1) == "a"
    assert m.span(1) == (2, 3)


def test_group_with_bound_repetition():
    m = fullmatch(r"(ab){2,3}", "abab")
    assert m.group(1) == "ab"
    assert m.span(1) == (2, 4)


def test_group_index_out_of_range_raises():
    m = fullmatch(r"(a)", "a")
    with pytest.raises(IndexError):
        m.group(2)


def test_group_search_captures():
    m = search(r"(\d+)-(\d+)", "id 42-7 done")
    assert m.groups() == ("42", "7")


# ---- matcher: search/findall -------------------------------------------

def test_search_finds_leftmost():
    m = search("bc", "abcabc")
    assert m.span() == (1, 3)


def test_search_no_match_returns_none():
    assert search("xyz", "abc") is None


def test_findall_multiple_matches():
    assert findall(r"\d+", "a12b345c6") == ["12", "345", "6"]


def test_findall_no_matches_returns_empty_list():
    assert findall("z+", "abc") == []


def test_findall_zero_width_pattern_does_not_hang():
    # a* can match the empty string; findall must still terminate.
    results = findall("a*", "bab")
    assert results == ["", "a", "", ""]


# ---- catastrophic-backtracking pattern stays fast ----------------------

def test_nested_star_pattern_is_linear_not_exponential():
    # A classic backtracking-engine killer: (a*)*b against a long run of
    # 'a's with no trailing 'b'. Thompson NFA simulation must reject this
    # quickly instead of exploring exponentially many paths.
    pat = Pattern("(a*)*b")
    text = "a" * 200
    assert pat.search(text) is None


# ---- CLI ----------------------------------------------------------------

def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "regexlite", *args],
        capture_output=True, text=True,
    )


def test_cli_match_success():
    result = _run_cli("match", "abc", "abcdef")
    assert result.returncode == 0
    assert "abc" in result.stdout


def test_cli_match_prints_groups():
    result = _run_cli("match", r"(\w+)@(\w+)", "alice@example", "--full")
    assert result.returncode == 0
    assert "group 1: 'alice'" in result.stdout
    assert "group 2: 'example'" in result.stdout


def test_cli_match_failure_exits_nonzero():
    result = _run_cli("match", "xyz", "abcdef")
    assert result.returncode == 1
    assert "no match" in result.stdout


def test_cli_findall():
    result = _run_cli("findall", r"\d+", "a12b345")
    assert result.returncode == 0
    assert "12" in result.stdout
    assert "345" in result.stdout


def test_cli_bad_pattern_exits_cleanly():
    result = _run_cli("match", "(abc", "abc")
    assert result.returncode == 1
    assert "error:" in result.stderr


def test_cli_grep(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("hello world\nfoo bar\nhello again\n")
    result = _run_cli("grep", "hello", str(f))
    assert result.returncode == 0
    assert "1:hello world" in result.stdout
    assert "3:hello again" in result.stdout
    assert "foo bar" not in result.stdout


def test_cli_grep_no_match_exits_nonzero(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("nothing here\n")
    result = _run_cli("grep", "zzz", str(f))
    assert result.returncode == 1


def test_cli_grep_missing_file_exits_cleanly():
    result = _run_cli("grep", "abc", "/no/such/file.txt")
    assert result.returncode == 1
    assert "error:" in result.stderr
