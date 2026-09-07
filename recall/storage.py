"""JSON-backed flashcard deck storage."""
import json
import os
import uuid
from datetime import date, timedelta

from .algorithm import CardState, review as sm2_review


def load_deck(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def save_deck(path, cards):
    with open(path, "w") as f:
        json.dump(cards, f, indent=2)


def add_card(cards, front, back, today=None):
    today = today or date.today()
    cards.append({
        "id": str(uuid.uuid4()),
        "front": front,
        "back": back,
        "interval_days": 0,
        "repetitions": 0,
        "ease_factor": 2.5,
        "due_date": today.isoformat(),
    })
    return cards


def due_cards(cards, today=None):
    today = today or date.today()
    return [c for c in cards if date.fromisoformat(c["due_date"]) <= today]


def import_cards(cards, lines, today=None):
    """Add cards from an iterable of 'front\\tback' lines.

    Blank lines and lines starting with '#' are skipped. Lines without a
    tab separator are skipped. Returns the number of cards added.
    """
    added = 0
    for line in lines:
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        if "\t" not in line:
            continue
        front, back = line.split("\t", 1)
        front, back = front.strip(), back.strip()
        if not front or not back:
            continue
        add_card(cards, front, back, today=today)
        added += 1
    return added


def export_lines(cards):
    """Return a list of 'front\\tback' lines, one per card."""
    return [f"{c['front']}\t{c['back']}" for c in cards]


def load_registry(path):
    """Load the name -> deck path mapping used for multi-deck support."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def save_registry(path, registry):
    with open(path, "w") as f:
        json.dump(registry, f, indent=2)


def register_deck(registry, name, deck_path):
    """Record that `name` refers to `deck_path`, overwriting any prior path."""
    registry[name] = deck_path
    return registry


def apply_review(card, quality, today=None):
    """Score a review and update the card's schedule in place."""
    today = today or date.today()
    state = CardState(card["interval_days"], card["repetitions"], card["ease_factor"])
    new_state = sm2_review(state, quality)
    card["interval_days"] = new_state.interval_days
    card["repetitions"] = new_state.repetitions
    card["ease_factor"] = new_state.ease_factor
    card["due_date"] = (today + timedelta(days=new_state.interval_days)).isoformat()
    return card
