from datetime import date, timedelta

import pytest

from recall.algorithm import CardState, review
from recall.__main__ import (
    build_arg_parser,
    main,
    run_add,
    run_decks,
    run_export,
    run_import,
    run_leeches,
    run_list,
    run_review,
    run_show,
    run_stats,
)
from recall.storage import (
    add_card,
    apply_review,
    due_cards,
    export_lines,
    import_cards,
    leech_cards,
    load_deck,
    load_registry,
    register_deck,
    save_deck,
    save_registry,
)


def test_review_failed_recall_resets_repetitions():
    state = CardState(interval_days=10, repetitions=3, ease_factor=2.3)
    new_state = review(state, quality=1)
    assert new_state.interval_days == 1
    assert new_state.repetitions == 0
    assert new_state.ease_factor == 2.3


def test_review_first_two_successes_use_fixed_intervals():
    state = CardState()
    after_first = review(state, quality=4)
    assert after_first.interval_days == 1
    assert after_first.repetitions == 1

    after_second = review(after_first, quality=4)
    assert after_second.interval_days == 6
    assert after_second.repetitions == 2


def test_review_third_success_scales_by_ease_factor():
    state = CardState(interval_days=6, repetitions=2, ease_factor=2.5)
    after_third = review(state, quality=5)
    assert after_third.repetitions == 3
    assert after_third.interval_days == round(6 * after_third.ease_factor)


def test_review_rejects_out_of_range_quality():
    with pytest.raises(ValueError):
        review(CardState(), quality=6)


def test_add_card_and_load_deck_roundtrip(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    cards = add_card([], "2+2", "4")
    save_deck(deck_path, cards)
    loaded = load_deck(deck_path)
    assert len(loaded) == 1
    assert loaded[0]["front"] == "2+2"
    assert loaded[0]["back"] == "4"
    assert loaded[0]["repetitions"] == 0


def test_load_deck_missing_file_returns_empty_list(tmp_path):
    assert load_deck(str(tmp_path / "missing.json")) == []


def test_due_cards_filters_by_date():
    today = date(2026, 1, 10)
    cards = add_card([], "front", "back", today=today)
    cards[0]["due_date"] = (today + timedelta(days=5)).isoformat()
    assert due_cards(cards, today=today) == []
    assert due_cards(cards, today=today + timedelta(days=5)) == cards


def test_apply_review_updates_due_date():
    today = date(2026, 1, 10)
    cards = add_card([], "front", "back", today=today)
    card = apply_review(cards[0], quality=4, today=today)
    assert card["due_date"] == (today + timedelta(days=1)).isoformat()
    assert card["repetitions"] == 1


def test_cli_add_persists_card(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    parser = build_arg_parser()
    args = parser.parse_args(["--deck", deck_path, "add", "capital of France", "Paris"])
    run_add(args)
    cards = load_deck(deck_path)
    assert len(cards) == 1
    assert cards[0]["front"] == "capital of France"


def test_cli_review_walks_due_cards_and_saves(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    save_deck(deck_path, add_card([], "front", "back"))
    parser = build_arg_parser()
    args = parser.parse_args(["--deck", deck_path, "review"])

    inputs = iter(["", "5"])
    outputs = []
    run_review(args, input_fn=lambda prompt="": next(inputs), print_fn=outputs.append)

    cards = load_deck(deck_path)
    assert cards[0]["repetitions"] == 1
    assert any("Reviewed 1 card" in line for line in outputs)


def test_cli_review_with_nothing_due_reports_that(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    save_deck(deck_path, [])
    parser = build_arg_parser()
    args = parser.parse_args(["--deck", deck_path, "review"])
    outputs = []
    run_review(args, print_fn=outputs.append)
    assert outputs == ["Nothing due for review."]


def test_cli_list_reports_empty_deck(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    save_deck(deck_path, [])
    parser = build_arg_parser()
    args = parser.parse_args(["--deck", deck_path, "list"])
    outputs = []
    run_list(args, print_fn=outputs.append)
    assert outputs == ["Deck is empty."]


def test_cli_list_sorts_by_due_date_and_marks_status(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    today = date(2026, 1, 10)
    cards = add_card([], "later", "back", today=today)
    cards = add_card(cards, "sooner", "back", today=today)
    cards[0]["due_date"] = (today + timedelta(days=5)).isoformat()
    cards[1]["due_date"] = today.isoformat()
    save_deck(deck_path, cards)
    parser = build_arg_parser()
    args = parser.parse_args(["--deck", deck_path, "list"])
    outputs = []
    run_list(args, print_fn=outputs.append, today=today)
    assert len(outputs) == 2
    assert "sooner" in outputs[0] and "due" in outputs[0]
    assert "later" in outputs[1] and "upcoming" in outputs[1]


def test_cli_list_match_filters_front_or_back_case_insensitively(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    today = date(2026, 1, 10)
    cards = add_card([], "Alpha", "needle inside", today=today)
    cards = add_card(cards, "Beta", "other", today=today)
    save_deck(deck_path, cards)
    args = build_arg_parser().parse_args(["--deck", deck_path, "list", "--match", "NEEDLE"])
    outputs = []
    run_list(args, print_fn=outputs.append, today=today)
    assert len(outputs) == 1 and "Alpha" in outputs[0]
    args = build_arg_parser().parse_args(["--deck", deck_path, "list", "--match", "zzz"])
    outputs = []
    run_list(args, print_fn=outputs.append, today=today)
    assert outputs == ["No matching cards."]


def test_cli_list_json_outputs_rows_and_empty_array(tmp_path):
    import json

    deck_path = str(tmp_path / "deck.json")
    today = date(2026, 1, 10)
    save_deck(deck_path, add_card(add_card([], "A", "x\ty", today=today), "B", "z", today=today))
    args = build_arg_parser().parse_args(["--deck", deck_path, "list", "--json", "--match", "x"])
    outputs = []
    run_list(args, print_fn=outputs.append, today=today)
    rows = json.loads(outputs[0])
    assert rows == [{"front": "A", "back": "x\ty", "due_date": rows[0]["due_date"], "due": True}]
    args = build_arg_parser().parse_args(["--deck", deck_path, "list", "--json", "--match", "zzz"])
    outputs = []
    run_list(args, print_fn=outputs.append, today=today)
    assert outputs == ["[]"]


def test_import_cards_adds_valid_lines_and_skips_bad_ones():
    lines = [
        "2+2\t4",
        "\n",
        "# a comment",
        "no tab here",
        "capital of France\tParis\n",
        "\tmissing front",
    ]
    cards = []
    added = import_cards(cards, lines)
    assert added == 2
    assert [c["front"] for c in cards] == ["2+2", "capital of France"]
    assert [c["back"] for c in cards] == ["4", "Paris"]


def test_export_lines_roundtrips_through_import():
    cards = add_card([], "front1", "back1")
    cards = add_card(cards, "front2", "back2")
    lines = export_lines(cards)
    assert lines == ["front1\tback1", "front2\tback2"]
    reimported = import_cards([], lines)
    assert reimported == 2


def test_cli_import_persists_cards_from_file(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    import_path = tmp_path / "cards.txt"
    import_path.write_text("2+2\t4\ncapital of France\tParis\n")
    parser = build_arg_parser()
    args = parser.parse_args(["--deck", deck_path, "import", str(import_path)])
    outputs = []
    run_import(args, print_fn=outputs.append)
    cards = load_deck(deck_path)
    assert len(cards) == 2
    assert any("Imported 2 card" in line for line in outputs)


def test_cli_export_writes_file(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    save_deck(deck_path, add_card([], "front", "back"))
    export_path = tmp_path / "out.txt"
    parser = build_arg_parser()
    args = parser.parse_args(["--deck", deck_path, "export", str(export_path)])
    outputs = []
    run_export(args, print_fn=outputs.append)
    assert export_path.read_text() == "front\tback\n"
    assert any("Exported 1 card" in line for line in outputs)


def test_cli_stats_reports_counts(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    save_deck(deck_path, add_card([], "front", "back"))
    parser = build_arg_parser()
    args = parser.parse_args(["--deck", deck_path, "stats"])
    outputs = []
    run_stats(args, print_fn=outputs.append)
    assert any("Total cards: 1" in line for line in outputs)
    assert any("Due today" in line for line in outputs)
    assert any("Leeches (4+ lapses): 0" in line for line in outputs)


def test_cli_stats_breaks_down_maturity_and_forecast(tmp_path):
    from datetime import date, timedelta
    deck_path = str(tmp_path / "deck.json")
    cards = add_card([], "new", "b")
    cards = add_card(cards, "young", "b")
    cards = add_card(cards, "old", "b")
    today = date.today()
    cards[1].update(repetitions=2, interval_days=6, ease_factor=2.0,
                    due_date=(today + timedelta(days=3)).isoformat())
    cards[2].update(repetitions=5, interval_days=30, ease_factor=3.0,
                    due_date=(today + timedelta(days=20)).isoformat())
    save_deck(deck_path, cards)
    args = build_arg_parser().parse_args(["--deck", deck_path, "stats"])
    outputs = []
    run_stats(args, print_fn=outputs.append)
    assert "New: 1, learning: 1, mature (21+ day interval): 1" in outputs
    assert "Average ease: 2.50" in outputs
    assert "Due in the next 7 days: 1" in outputs


def test_apply_review_failure_increments_lapses():
    cards = add_card([], "front", "back")
    apply_review(cards[0], quality=1)
    assert cards[0]["lapses"] == 1
    apply_review(cards[0], quality=1)
    assert cards[0]["lapses"] == 2


def test_apply_review_success_does_not_increment_lapses():
    cards = add_card([], "front", "back")
    apply_review(cards[0], quality=1)
    apply_review(cards[0], quality=5)
    assert cards[0]["lapses"] == 1


def test_leech_cards_filters_by_threshold_and_sorts_worst_first():
    cards = add_card([], "easy", "back")
    cards = add_card(cards, "hard", "back")
    cards[0]["lapses"] = 3
    cards[1]["lapses"] = 6
    leeches = leech_cards(cards, threshold=4)
    assert [c["front"] for c in leeches] == ["hard"]


def test_leech_cards_treats_missing_lapses_field_as_zero():
    cards = add_card([], "front", "back")
    del cards[0]["lapses"]
    assert leech_cards(cards, threshold=1) == []


def test_cli_leeches_reports_none_below_threshold(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    save_deck(deck_path, add_card([], "front", "back"))
    parser = build_arg_parser()
    args = parser.parse_args(["--deck", deck_path, "leeches"])
    outputs = []
    run_leeches(args, print_fn=outputs.append)
    assert outputs == ["No leeches (threshold: 4 lapses)."]


def test_cli_leeches_lists_cards_past_threshold(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    cards = add_card([], "front", "back")
    cards[0]["lapses"] = 5
    save_deck(deck_path, cards)
    parser = build_arg_parser()
    args = parser.parse_args(["--deck", deck_path, "leeches", "--threshold", "2"])
    outputs = []
    run_leeches(args, print_fn=outputs.append)
    assert any("[5 lapses] front" in line for line in outputs)


def test_registry_roundtrip(tmp_path):
    registry_path = str(tmp_path / "registry.json")
    registry = register_deck({}, "spanish", "spanish.json")
    save_registry(registry_path, registry)
    assert load_registry(registry_path) == {"spanish": "spanish.json"}


def test_load_registry_missing_file_returns_empty_dict(tmp_path):
    assert load_registry(str(tmp_path / "missing.json")) == {}


def test_register_deck_overwrites_existing_name():
    registry = register_deck({}, "spanish", "old.json")
    register_deck(registry, "spanish", "new.json")
    assert registry == {"spanish": "new.json"}


def test_cli_add_registers_deck_under_its_basename(tmp_path):
    deck_path = str(tmp_path / "spanish.json")
    registry_path = str(tmp_path / "registry.json")
    main(["--deck", deck_path, "--registry", registry_path, "add", "hola", "hello"])
    assert load_registry(registry_path) == {"spanish": deck_path}


def test_cli_add_registers_deck_under_explicit_name(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    registry_path = str(tmp_path / "registry.json")
    main([
        "--deck", deck_path, "--deck-name", "custom", "--registry", registry_path,
        "add", "front", "back",
    ])
    assert load_registry(registry_path) == {"custom": deck_path}


def test_cli_decks_lists_registered_decks_with_counts(tmp_path):
    spanish_path = str(tmp_path / "spanish.json")
    french_path = str(tmp_path / "french.json")
    save_deck(spanish_path, add_card([], "hola", "hello"))
    save_deck(french_path, add_card(add_card([], "bonjour", "hello"), "merci", "thanks"))
    registry_path = str(tmp_path / "registry.json")
    registry = register_deck({}, "spanish", spanish_path)
    register_deck(registry, "french", french_path)
    save_registry(registry_path, registry)

    parser = build_arg_parser()
    args = parser.parse_args(["--registry", registry_path, "decks"])
    outputs = []
    run_decks(args, print_fn=outputs.append)
    assert any(line.startswith("french: 2 card(s)") for line in outputs)
    assert any(line.startswith("spanish: 1 card(s)") for line in outputs)


def test_cli_decks_flags_missing_deck_file(tmp_path):
    gone = str(tmp_path / "gone.json")
    registry_path = str(tmp_path / "registry.json")
    save_registry(registry_path, register_deck({}, "gone", gone))
    args = build_arg_parser().parse_args(["--registry", registry_path, "decks"])
    outputs = []
    run_decks(args, print_fn=outputs.append)
    assert outputs == [f"gone: deck file missing  ({gone})"]


def test_cli_decks_reports_when_nothing_registered(tmp_path):
    parser = build_arg_parser()
    args = parser.parse_args(["--registry", str(tmp_path / "missing.json"), "decks"])
    outputs = []
    run_decks(args, print_fn=outputs.append)
    assert outputs == ["No decks registered yet."]


def test_version():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "recall", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout or "0.1" in result.stdout


def test_cli_show_prints_due_backs_without_changing_deck(tmp_path):
    deck = str(tmp_path / "deck.json")
    cards = []
    add_card(cards, "capital of France?", "Paris")
    save_deck(deck, cards)
    args = build_arg_parser().parse_args(["--deck", deck, "show"])
    outputs = []
    run_show(args, print_fn=outputs.append)
    assert "Q: capital of France?" in outputs
    assert "A: Paris\n" in outputs
    assert load_deck(deck) == cards


def test_cli_show_rate_reschedules_due_cards(tmp_path):
    deck = str(tmp_path / "deck.json")
    cards = []
    add_card(cards, "q", "a")
    save_deck(deck, cards)
    args = build_arg_parser().parse_args(["--deck", deck, "show", "--rate", "5"])
    run_show(args, print_fn=lambda *_: None)
    assert due_cards(load_deck(deck)) == []


def test_cli_show_limit_caps_cards_shown_and_rated(tmp_path):
    deck = str(tmp_path / "deck.json")
    cards = []
    for n in range(3):
        add_card(cards, f"q{n}", f"a{n}")
    save_deck(deck, cards)
    args = build_arg_parser().parse_args(["--deck", deck, "show", "--limit", "1", "--rate", "5"])
    outputs = []
    run_show(args, print_fn=outputs.append)
    assert sum(o.startswith("Q: ") for o in outputs) == 1
    assert len(due_cards(load_deck(deck))) == 2


def test_import_skips_fronts_already_in_deck():
    cards = []
    add_card(cards, "What is SM-2?", "an algorithm")
    added = import_cards(cards, ["what is  sm-2?\tdup\n", "New\tcard\n", "New\tagain\n"])
    assert added == 1
    assert [c["front"] for c in cards] == ["What is SM-2?", "New"]


def test_cli_add_skips_duplicate_front(tmp_path, capsys):
    deck = str(tmp_path / "d.json")
    reg = str(tmp_path / "r.json")
    main(["--deck", deck, "--registry", reg, "add", "Q", "A"])
    main(["--deck", deck, "--registry", reg, "add", "q", "B"])
    assert "Skipped" in capsys.readouterr().out
    main(["--deck", deck, "--registry", reg, "stats"])
    assert "Total cards: 1" in capsys.readouterr().out


def test_cli_add_rejects_blank_front_or_back(tmp_path, capsys):
    deck = str(tmp_path / "d.json")
    reg = str(tmp_path / "r.json")
    for front, back in [("", "A"), ("   ", "A"), ("Q", " ")]:
        with pytest.raises(SystemExit) as exc:
            main(["--deck", deck, "--registry", reg, "add", front, back])
        assert exc.value.code == 1
        assert "must not be blank" in capsys.readouterr().err
    assert load_deck(deck) == []


def test_rate_updates_only_the_matched_card(tmp_path, capsys):
    deck = str(tmp_path / "d.json")
    reg = str(tmp_path / "r.json")
    main(["--deck", deck, "--registry", reg, "add", "Alpha thing", "a"])
    main(["--deck", deck, "--registry", reg, "add", "Beta thing", "b"])
    main(["--deck", deck, "--registry", reg, "rate", "alpha", "1"])
    cards = {c["front"]: c for c in load_deck(deck)}
    assert cards["Alpha thing"]["lapses"] == 1
    assert cards["Beta thing"].get("lapses", 0) == 0


def test_rate_rejects_ambiguous_or_missing_match(tmp_path, capsys):
    import pytest
    deck = str(tmp_path / "d.json")
    reg = str(tmp_path / "r.json")
    main(["--deck", deck, "--registry", reg, "add", "Alpha thing", "a"])
    main(["--deck", deck, "--registry", reg, "add", "Beta thing", "b"])
    for needle in ("thing", "zzz"):
        with pytest.raises(SystemExit):
            main(["--deck", deck, "--registry", reg, "rate", needle, "5"])
    assert all(c.get("lapses", 0) == 0 for c in load_deck(deck))


def test_cli_list_due_hides_upcoming_cards(tmp_path):
    deck_path = str(tmp_path / "deck.json")
    today = date(2026, 1, 10)
    cards = add_card([], "later", "back", today=today)
    cards = add_card(cards, "sooner", "back", today=today)
    cards[0]["due_date"] = (today + timedelta(days=5)).isoformat()
    cards[1]["due_date"] = today.isoformat()
    save_deck(deck_path, cards)
    args = build_arg_parser().parse_args(["--deck", deck_path, "list", "--due"])
    outputs = []
    run_list(args, print_fn=outputs.append, today=today)
    assert len(outputs) == 1 and "sooner" in outputs[0]
    cards[1]["due_date"] = (today + timedelta(days=1)).isoformat()
    save_deck(deck_path, cards)
    outputs = []
    run_list(args, print_fn=outputs.append, today=today)
    assert outputs == ["No cards due."]


def test_delete_removes_only_the_matched_card(tmp_path):
    deck = str(tmp_path / "d.json")
    reg = str(tmp_path / "r.json")
    main(["--deck", deck, "--registry", reg, "add", "Alpha thing", "a"])
    main(["--deck", deck, "--registry", reg, "add", "Beta thing", "b"])
    main(["--deck", deck, "--registry", reg, "delete", "alpha"])
    assert [c["front"] for c in load_deck(deck)] == ["Beta thing"]


def test_delete_rejects_ambiguous_or_missing_match(tmp_path):
    deck = str(tmp_path / "d.json")
    reg = str(tmp_path / "r.json")
    main(["--deck", deck, "--registry", reg, "add", "Alpha thing", "a"])
    main(["--deck", deck, "--registry", reg, "add", "Beta thing", "b"])
    for needle in ("thing", "zzz"):
        with pytest.raises(SystemExit):
            main(["--deck", deck, "--registry", reg, "delete", needle])
    assert len(load_deck(deck)) == 2


def test_edit_rewrites_text_but_keeps_schedule(tmp_path):
    deck = str(tmp_path / "d.json")
    reg = str(tmp_path / "r.json")
    main(["--deck", deck, "--registry", reg, "add", "Alpha thing", "a"])
    main(["--deck", deck, "--registry", reg, "add", "Beta thing", "b"])
    main(["--deck", deck, "--registry", reg, "rate", "alpha", "5"])
    before = load_deck(deck)[0]
    main(["--deck", deck, "--registry", reg, "edit", "alpha", "--back", "A2", "--front", "Alpha v2"])
    after = load_deck(deck)[0]
    assert (after["front"], after["back"]) == ("Alpha v2", "A2")
    for k in ("id", "due_date", "interval_days", "repetitions", "ease_factor"):
        assert after[k] == before[k]


def test_edit_rejects_bad_input_and_leaves_deck_alone(tmp_path):
    deck = str(tmp_path / "d.json")
    reg = str(tmp_path / "r.json")
    main(["--deck", deck, "--registry", reg, "add", "Alpha thing", "a"])
    main(["--deck", deck, "--registry", reg, "add", "Beta thing", "b"])
    orig = load_deck(deck)
    for argv in (["edit", "alpha"], ["edit", "alpha", "--back", "  "],
                 ["edit", "thing", "--back", "x"], ["edit", "zzz", "--back", "x"],
                 ["edit", "alpha", "--front", "beta THING"]):
        with pytest.raises(SystemExit):
            main(["--deck", deck, "--registry", reg] + argv)
    assert load_deck(deck) == orig


def test_import_reports_malformed_line_numbers_and_missing_file(tmp_path, capsys):
    deck = str(tmp_path / "d.json")
    src = tmp_path / "in.txt"
    src.write_text("q1\ta1\nnotab\n# c\n\tback only\nfront only\t\n")
    parser = build_arg_parser()
    run_import(parser.parse_args(["--deck", deck, "import", str(src)]), print_fn=lambda m: None)
    err = capsys.readouterr().err
    assert "skipped 3 malformed line(s)" in err and "2, 4, 5" in err
    with pytest.raises(SystemExit) as exc:
        run_import(parser.parse_args(["--deck", deck, "import", str(tmp_path / "nope.txt")]))
    assert exc.value.code == 1
    assert "cannot read" in capsys.readouterr().err


def test_export_import_roundtrips_tabs_newlines_backslashes_and_hash():
    from recall.storage import add_card, export_lines, import_cards
    src = []
    add_card(src, "#1 q\\n", "a\tb\nc\\")
    lines = export_lines(src)
    assert len(lines) == 1 and "\n" not in lines[0] and lines[0].count("\t") == 1
    dst = []
    assert import_cards(dst, lines) == 1
    assert (dst[0]["front"], dst[0]["back"]) == ("#1 q\\n", "a\tb\nc\\")


def test_cli_show_negative_limit_is_an_error(tmp_path, capsys):
    deck = str(tmp_path / "deck.json")
    cards = []
    add_card(cards, "q", "a")
    save_deck(deck, cards)
    args = build_arg_parser().parse_args(["--deck", deck, "show", "--limit", "-1"])
    try:
        run_show(args, print_fn=lambda *_: None)
        raised = False
    except SystemExit as e:
        raised = e.code == 1
    assert raised
    assert "--limit" in capsys.readouterr().err
