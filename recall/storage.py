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
        "lapses": 0,
    })
    return cards


def has_front(cards, front):
    """True if some card already has this front (case/whitespace-insensitive)."""
    key = " ".join(front.split()).casefold()
    return any(" ".join(c["front"].split()).casefold() == key for c in cards)


def due_cards(cards, today=None):
    today = today or date.today()
    return [c for c in cards if date.fromisoformat(c["due_date"]) <= today]


_ESC = {"\\": "\\", "t": "\t", "n": "\n", "r": "\r", "#": "#"}


def _escape(text):
    out = text.replace("\\", "\\\\").replace("\t", "\\t")
    out = out.replace("\n", "\\n").replace("\r", "\\r")
    return "\\" + out if out.startswith("#") else out


def _unescape(text):
    out, i = [], 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] in _ESC:
            out.append(_ESC[text[i + 1]])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def import_cards(cards, lines, today=None, malformed=None):
    """Add cards from an iterable of 'front\\tback' lines.

    Blank lines and lines starting with '#' are skipped. Lines without a
    tab separator are skipped, as are lines whose front matches an existing
    card. Returns the number of cards added. If `malformed` is a list, the
    1-based line numbers of lines that were skipped for lacking a tab or a
    front/back are appended to it (duplicates and comments are not).
    """
    added = 0
    for lineno, line in enumerate(lines, 1):
        line = line.rstrip("\n")
        if not line.strip() or line.startswith("#"):
            continue
        front, sep, back = line.partition("\t")
        front, back = front.strip(), back.strip()
        if not sep or not front or not back:
            if malformed is not None:
                malformed.append(lineno)
            continue
        front, back = _unescape(front), _unescape(back)
        if has_front(cards, front):
            continue
        add_card(cards, front, back, today=today)
        added += 1
    return added


def export_lines(cards):
    """Return a list of 'front\\tback' lines, one per card.

    Tabs, newlines and backslashes inside a card are written as \\t, \\n
    and \\\\ (and a leading '#' as \\#) so the line survives import.
    """
    return [f"{_escape(c['front'])}\t{_escape(c['back'])}" for c in cards]


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
    if quality < 3:
        card["lapses"] = card.get("lapses", 0) + 1
    return card


def leech_cards(cards, threshold=4):
    """Return cards whose lapse count has reached `threshold`, worst-first.

    A "leech" (the Anki term) is a card that keeps getting forgotten despite
    repeated review -- usually a sign the card itself is malformed (too
    vague, testing two facts at once) rather than a memory problem.
    """
    leeches = [c for c in cards if c.get("lapses", 0) >= threshold]
    return sorted(leeches, key=lambda c: c.get("lapses", 0), reverse=True)
