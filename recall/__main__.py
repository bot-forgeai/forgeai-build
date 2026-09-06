"""Command-line interface for recall: add flashcards, review due ones, see stats."""
import argparse
import sys
from datetime import date

from .storage import (
    add_card,
    apply_review,
    due_cards,
    export_lines,
    import_cards,
    load_deck,
    save_deck,
)


def build_arg_parser():
    parser = argparse.ArgumentParser(prog="recall", description=__doc__)
    parser.add_argument("--deck", default="recall_deck.json", help="path to the deck JSON file")
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="add a new flashcard")
    add_p.add_argument("front", help="the question / prompt side")
    add_p.add_argument("back", help="the answer side")

    sub.add_parser("review", help="review all cards currently due")
    sub.add_parser("stats", help="show deck size and how many cards are due")
    sub.add_parser("list", help="preview all cards sorted by due date, without reviewing them")

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
    cards = load_deck(args.deck)
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


def run_list(args, print_fn=print, today=None):
    cards = load_deck(args.deck)
    if not cards:
        print_fn("Deck is empty.")
        return
    today = today or date.today()
    for card in sorted(cards, key=lambda c: c["due_date"]):
        status = "due" if date.fromisoformat(card["due_date"]) <= today else "upcoming"
        print_fn(f"[{status:>8}] {card['due_date']}  {card['front']}")


def run_import(args, print_fn=print):
    cards = load_deck(args.deck)
    with open(args.path) as f:
        added = import_cards(cards, f)
    save_deck(args.deck, cards)
    print_fn(f"Imported {added} card(s). Deck now has {len(cards)} card(s).")


def run_export(args, print_fn=print):
    cards = load_deck(args.deck)
    lines = export_lines(cards)
    with open(args.path, "w") as f:
        f.write("\n".join(lines) + ("\n" if lines else ""))
    print_fn(f"Exported {len(lines)} card(s) to {args.path}.")


def run_stats(args, print_fn=print):
    cards = load_deck(args.deck)
    due = due_cards(cards)
    print_fn(f"Deck: {args.deck}")
    print_fn(f"Total cards: {len(cards)}")
    print_fn(f"Due today ({date.today().isoformat()}): {len(due)}")


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.command == "add":
        run_add(args)
    elif args.command == "review":
        run_review(args)
    elif args.command == "stats":
        run_stats(args)
    elif args.command == "list":
        run_list(args)
    elif args.command == "import":
        run_import(args)
    elif args.command == "export":
        run_export(args)


if __name__ == "__main__":
    main()
