"""Command-line interface for recall: add flashcards, review due ones, see stats."""
import argparse
import json
import os
import sys
from datetime import date, timedelta
from importlib.metadata import version as _get_version, PackageNotFoundError

from .storage import (
    add_card,
    has_front,
    apply_review,
    due_cards,
    forecast_counts,
    export_lines,
    import_cards,
    leech_cards,
    load_deck,
    load_registry,
    register_deck,
    save_deck,
    save_registry,
)


def _get_package_version():
    try:
        return _get_version("eulerlib")
    except PackageNotFoundError:
        return "0.1.0"


def build_arg_parser():
    parser = argparse.ArgumentParser(prog="recall", description=__doc__)
    parser.add_argument("--version", action="version", version=_get_package_version())
    parser.add_argument("--deck", default="recall_deck.json", help="path to the deck JSON file")
    parser.add_argument(
        "--deck-name",
        default=None,
        help="name this deck is registered under (default: the deck file's basename)",
    )
    parser.add_argument(
        "--registry",
        default="recall_registry.json",
        help="path to the multi-deck registry file",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="add a new flashcard")
    add_p.add_argument("front", help="the question / prompt side")
    add_p.add_argument("back", help="the answer side")

    sub.add_parser("review", help="review all cards currently due")
    show_p = sub.add_parser(
        "show", help="print due cards (front and back) without prompting; for non-interactive use"
    )
    show_p.add_argument(
        "--rate", type=int, choices=range(6), metavar="0-5", default=None,
        help="also record this recall quality for every card shown",
    )
    show_p.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="show (and rate) at most N due cards, so --rate doesn't grade cards you haven't seen",
    )
    rate_p = sub.add_parser(
        "rate", help="record a recall quality for one card, picked by a substring of its front"
    )
    rate_p.add_argument("text", help="substring of the card's front (case-insensitive); must match exactly one card")
    rate_p.add_argument("quality", type=int, choices=range(6), metavar="0-5", help="recall quality")
    del_p = sub.add_parser(
        "delete", help="remove one card, picked by a substring of its front"
    )
    del_p.add_argument("text", help="substring of the card's front (case-insensitive); must match exactly one card")
    edit_p = sub.add_parser(
        "edit", help="rewrite one card's front and/or back, keeping its review schedule"
    )
    edit_p.add_argument("text", help="substring of the card's front (case-insensitive); must match exactly one card")
    edit_p.add_argument("--front", default=None, help="new front text")
    edit_p.add_argument("--back", default=None, help="new back text")
    stats_p = sub.add_parser("stats", help="show deck size and how many cards are due")
    stats_p.add_argument("--json", action="store_true", help="print the counts as a JSON object")
    fc_p = sub.add_parser("forecast", help="show how many cards fall due on each of the next N days")
    fc_p.add_argument("--days", type=int, default=7, help="days ahead to show (default 7)")
    fc_p.add_argument("--json", action="store_true", help="print [{date, due}] as JSON")
    p_list = sub.add_parser("list", help="preview all cards sorted by due date, without reviewing them")
    p_list.add_argument("--due", action="store_true", help="only list cards that are due today or overdue")
    p_list.add_argument("--match", default=None, metavar="TEXT", help="only list cards whose front or back contains TEXT")
    p_list.add_argument("--json", action="store_true", help="print matching cards as a JSON array (front, back, due_date, due)")
    sub.add_parser("decks", help="list every deck registered so far, with its card counts")

    leeches_p = sub.add_parser(
        "leeches", help="list cards that keep getting forgotten despite review (candidates to rewrite or delete)"
    )
    leeches_p.add_argument(
        "--threshold", type=int, default=4,
        help="minimum lapse count to count as a leech (default: 4, matching Anki's default)",
    )

    import_p = sub.add_parser(
        "import", help="add cards from a text file of 'front<TAB>back' lines"
    )
    import_p.add_argument("path", help="path to the text file to import")

    export_p = sub.add_parser(
        "export", help="write all cards to a text file of 'front<TAB>back' lines"
    )
    export_p.add_argument("path", help="path to write the text file to")

    return parser


def run_add(args):
    if not args.front.strip() or not args.back.strip():
        print("error: card front and back must not be blank", file=sys.stderr)
        sys.exit(1)
    cards = load_deck(args.deck)
    if has_front(cards, args.front):
        print(f"Skipped: a card with this front already exists: {args.front}")
        return
    add_card(cards, args.front, args.back)
    save_deck(args.deck, cards)
    print(f"Added card. Deck now has {len(cards)} card(s).")


def run_review(args, input_fn=input, print_fn=print):
    cards = load_deck(args.deck)
    due = due_cards(cards)
    if not due:
        print_fn("Nothing due for review.")
        return
    for card in due:
        print_fn(f"\nQ: {card['front']}")
        input_fn("(press enter to reveal) ")
        print_fn(f"A: {card['back']}")
        while True:
            raw = input_fn("Quality of recall 0-5 (0=blackout, 5=perfect): ")
            try:
                quality = int(raw)
                if 0 <= quality <= 5:
                    break
            except ValueError:
                pass
            print_fn("Enter a number from 0 to 5.")
        apply_review(card, quality)
    save_deck(args.deck, cards)
    print_fn(f"\nReviewed {len(due)} card(s).")


def run_show(args, print_fn=print):
    if args.limit is not None and args.limit < 0:
        print("error: --limit must be 0 or more", file=sys.stderr)
        sys.exit(1)
    cards = load_deck(args.deck)
    due = due_cards(cards)
    if not due:
        print_fn("Nothing due for review.")
        return
    if args.limit is not None:
        due = due[:args.limit]
    for card in due:
        print_fn(f"Q: {card['front']}")
        print_fn(f"A: {card['back']}\n")
        if args.rate is not None:
            apply_review(card, args.rate)
    if args.rate is not None:
        save_deck(args.deck, cards)
        print_fn(f"Rated {len(due)} card(s) {args.rate}.")


def run_rate(args, print_fn=print):
    cards = load_deck(args.deck)
    needle = args.text.casefold()
    matches = [c for c in cards if needle in c["front"].casefold()]
    if len(matches) != 1:
        print_fn(f"{len(matches)} cards match {args.text!r}; need exactly 1.")
        for c in matches:
            print_fn(f"  {c['front']}")
        return False
    apply_review(matches[0], args.quality)
    save_deck(args.deck, cards)
    print_fn(f"Rated {matches[0]['front']!r} {args.quality}; next due {matches[0]['due_date']}.")
    return True


def run_delete(args, print_fn=print):
    cards = load_deck(args.deck)
    needle = args.text.casefold()
    matches = [c for c in cards if needle in c["front"].casefold()]
    if len(matches) != 1:
        print_fn(f"{len(matches)} cards match {args.text!r}; need exactly 1.")
        for c in matches:
            print_fn(f"  {c['front']}")
        return False
    cards.remove(matches[0])
    save_deck(args.deck, cards)
    print_fn(f"Deleted {matches[0]['front']!r}. Deck now has {len(cards)} card(s).")
    return True


def run_edit(args, print_fn=print):
    if args.front is None and args.back is None:
        print("error: edit needs --front and/or --back", file=sys.stderr)
        sys.exit(1)
    for val in (args.front, args.back):
        if val is not None and not val.strip():
            print("error: card front and back must not be blank", file=sys.stderr)
            sys.exit(1)
    cards = load_deck(args.deck)
    needle = args.text.casefold()
    matches = [c for c in cards if needle in c["front"].casefold()]
    if len(matches) != 1:
        print_fn(f"{len(matches)} cards match {args.text!r}; need exactly 1.")
        for c in matches:
            print_fn(f"  {c['front']}")
        return False
    card = matches[0]
    if args.front is not None and has_front([c for c in cards if c is not card], args.front):
        print(f"error: another card already has the front {args.front!r}", file=sys.stderr)
        sys.exit(1)
    old = card["front"]
    if args.front is not None:
        card["front"] = args.front
    if args.back is not None:
        card["back"] = args.back
    save_deck(args.deck, cards)
    print_fn(f"Edited {old!r}; schedule unchanged (due {card['due_date']}).")
    return True


def run_list(args, print_fn=print, today=None):
    cards = load_deck(args.deck)
    as_json = getattr(args, "json", False)
    if not cards:
        print_fn("[]" if as_json else "Deck is empty.")
        return
    today = today or date.today()
    shown = 0
    rows = []
    for card in sorted(cards, key=lambda c: c["due_date"]):
        is_due = date.fromisoformat(card["due_date"]) <= today
        if getattr(args, "due", False) and not is_due:
            continue
        match = getattr(args, "match", None)
        if match and match.casefold() not in (card["front"] + "\n" + card["back"]).casefold():
            continue
        shown += 1
        if as_json:
            rows.append({"front": card["front"], "back": card["back"], "due_date": card["due_date"], "due": is_due})
            continue
        status = "due" if is_due else "upcoming"
        print_fn(f"[{status:>8}] {card['due_date']}  {card['front']}")
    if as_json:
        print_fn(json.dumps(rows))
    elif not shown:
        print_fn("No matching cards." if getattr(args, "match", None) or not getattr(args, "due", False) else "No cards due.")


def run_import(args, print_fn=print):
    cards = load_deck(args.deck)
    try:
        with open(args.path) as f:
            malformed = []
            added = import_cards(cards, f, malformed=malformed)
    except OSError as e:
        print(f"error: cannot read {args.path}: {e.strerror}", file=sys.stderr)
        sys.exit(1)
    save_deck(args.deck, cards)
    print_fn(f"Imported {added} card(s). Deck now has {len(cards)} card(s).")
    if malformed:
        shown = ", ".join(map(str, malformed[:10])) + (", ..." if len(malformed) > 10 else "")
        print(f"warning: skipped {len(malformed)} malformed line(s) (need 'front<TAB>back'): {shown}", file=sys.stderr)


def run_export(args, print_fn=print):
    cards = load_deck(args.deck)
    lines = export_lines(cards)
    with open(args.path, "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    print_fn(f"Exported {len(lines)} card(s) to {args.path}.")


def run_stats(args, print_fn=print):
    cards = load_deck(args.deck)
    due = due_cards(cards)
    leeches = leech_cards(cards)
    if args.json:
        new = sum(1 for c in cards if c["repetitions"] == 0 and c.get("lapses", 0) == 0)
        mature = sum(1 for c in cards if c["interval_days"] >= 21)
        today = date.today()
        print_fn(json.dumps({
            "deck": args.deck, "total": len(cards), "due": len(due), "leeches": len(leeches),
            "new": new, "mature": mature, "learning": len(cards) - new - mature,
            "average_ease": round(sum(c["ease_factor"] for c in cards) / len(cards), 2) if cards else None,
            "due_next_7_days": sum(1 for c in cards if today < date.fromisoformat(c["due_date"]) <= today + timedelta(days=7)),
        }))
        return
    print_fn(f"Deck: {args.deck}")
    print_fn(f"Total cards: {len(cards)}")
    print_fn(f"Due today ({date.today().isoformat()}): {len(due)}")
    print_fn(f"Leeches (4+ lapses): {len(leeches)}")
    if not cards:
        return
    new = sum(1 for c in cards if c["repetitions"] == 0 and c.get("lapses", 0) == 0)
    mature = sum(1 for c in cards if c["interval_days"] >= 21)
    print_fn(f"New: {new}, learning: {len(cards) - new - mature}, mature (21+ day interval): {mature}")
    ease = sum(c["ease_factor"] for c in cards) / len(cards)
    print_fn(f"Average ease: {ease:.2f}")
    today = date.today()
    soon = sum(1 for c in cards if today < date.fromisoformat(c["due_date"]) <= today + timedelta(days=7))
    print_fn(f"Due in the next 7 days: {soon}")


def run_forecast(args, print_fn=print, today=None):
    if args.days < 0:
        print("--days must be 0 or more", file=sys.stderr)
        sys.exit(2)
    rows = forecast_counts(load_deck(args.deck), days=args.days, today=today)
    if args.json:
        print_fn(json.dumps([{"date": d.isoformat(), "due": n} for d, n in rows]))
        return
    for d, n in rows:
        print_fn(f"{d.isoformat()} {d.strftime('%a')}  {n:3d} {'#' * min(n, 40)}")


def run_leeches(args, print_fn=print):
    cards = load_deck(args.deck)
    leeches = leech_cards(cards, threshold=args.threshold)
    if not leeches:
        print_fn(f"No leeches (threshold: {args.threshold} lapses).")
        return
    for card in leeches:
        print_fn(f"[{card.get('lapses', 0)} lapses] {card['front']}")


def deck_name_for(args):
    return args.deck_name or os.path.splitext(os.path.basename(args.deck))[0]


def register_current_deck(args):
    """Record args.deck in the registry under its name, creating the registry if needed."""
    registry = load_registry(args.registry)
    register_deck(registry, deck_name_for(args), args.deck)
    save_registry(args.registry, registry)


def run_decks(args, print_fn=print):
    registry = load_registry(args.registry)
    if not registry:
        print_fn("No decks registered yet.")
        return
    today = date.today()
    for name, path in sorted(registry.items()):
        if not os.path.exists(path):
            print_fn(f"{name}: deck file missing  ({path})")
            continue
        cards = load_deck(path)
        due = due_cards(cards, today=today)
        print_fn(f"{name}: {len(cards)} card(s), {len(due)} due  ({path})")


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.command == "add":
        run_add(args)
        register_current_deck(args)
    elif args.command == "review":
        run_review(args)
        register_current_deck(args)
    elif args.command == "show":
        run_show(args)
        if args.rate is not None:
            register_current_deck(args)
    elif args.command == "rate":
        if run_rate(args):
            register_current_deck(args)
        else:
            sys.exit(1)
    elif args.command == "delete":
        if run_delete(args):
            register_current_deck(args)
        else:
            sys.exit(1)
    elif args.command == "edit":
        if run_edit(args):
            register_current_deck(args)
        else:
            sys.exit(1)
    elif args.command == "stats":
        run_stats(args)
    elif args.command == "forecast":
        run_forecast(args)
    elif args.command == "list":
        run_list(args)
    elif args.command == "import":
        run_import(args)
        register_current_deck(args)
    elif args.command == "export":
        run_export(args)
    elif args.command == "decks":
        run_decks(args)
    elif args.command == "leeches":
        run_leeches(args)


if __name__ == "__main__":
    main()
