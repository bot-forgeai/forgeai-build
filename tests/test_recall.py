from datetime import date, timedelta

import pytest

from recall.algorithm import CardState, review
from recall.__main__ import (
    build_arg_parser,
    run_add,
    run_export,
    run_import,
    run_list,
    run_review,
    run_stats,
)
from recall.storage import (
    add_card,
    apply_review,
    due_cards,
    export_lines,
    import_cards,
    load_deck,
    save_deck,
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
