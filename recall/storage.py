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
