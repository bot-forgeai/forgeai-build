"""SM-2 spaced-repetition scheduling (the algorithm behind SuperMemo 2 / Anki).

Given a card's current state and a 0-5 recall-quality rating, computes
the next review interval, repetition count, and ease factor.
"""
from dataclasses import dataclass


@dataclass
class CardState:
    interval_days: int = 0
    repetitions: int = 0
    ease_factor: float = 2.5


def review(state: CardState, quality: int) -> CardState:
    """Return the next CardState after a review rated 0 (blackout) to 5 (perfect)."""
    if not 0 <= quality <= 5:
        raise ValueError("quality must be between 0 and 5")

    if quality < 3:
        # Failed recall: reset repetitions, keep ease factor, review again tomorrow.
        return CardState(interval_days=1, repetitions=0, ease_factor=state.ease_factor)

    ease_factor = state.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(1.3, ease_factor)

    repetitions = state.repetitions + 1
    if repetitions == 1:
        interval_days = 1
    elif repetitions == 2:
        interval_days = 6
    else:
        interval_days = round(state.interval_days * ease_factor)

    return CardState(interval_days=interval_days, repetitions=repetitions, ease_factor=ease_factor)
