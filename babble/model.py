"""Order-N word-level Markov chain: train on text, generate new text."""
import random
from collections import Counter, defaultdict


def _weighted_choice(rng, counter):
    words = list(counter.keys())
    weights = list(counter.values())
    return rng.choices(words, weights=weights, k=1)[0]


class MarkovModel:
    def __init__(self, order=2):
        if order < 1:
            raise ValueError("order must be >= 1")
        self.order = order
        self.chain = defaultdict(Counter)
        self.starts = Counter()

    def train(self, text):
        for line in text.splitlines():
            words = line.split()
            if len(words) <= self.order:
                continue
            self.starts[tuple(words[: self.order])] += 1
            for i in range(len(words) - self.order):
                state = tuple(words[i : i + self.order])
                nxt = words[i + self.order]
                self.chain[state][nxt] += 1

    def generate(self, length=50, rng=None, seed=None):
        rng = rng or random.Random()
        if seed is not None:
            state = tuple(seed.split())
            if len(state) != self.order:
                raise ValueError(
                    f"seed must have exactly {self.order} word(s), got {len(state)}"
                )
        else:
            if not self.starts:
                return ""
            state = _weighted_choice(rng, self.starts)

        words = list(state)
        while len(words) < length:
            choices = self.chain.get(state)
            if not choices:
                break
            nxt = _weighted_choice(rng, choices)
            words.append(nxt)
            state = tuple(words[-self.order :])
        return " ".join(words)

    def merge(self, other):
        if other.order != self.order:
            raise ValueError(
                f"cannot merge order-{other.order} model into order-{self.order} model"
            )
        for state, counter in other.chain.items():
            self.chain[state].update(counter)
        self.starts.update(other.starts)

    def vocab_size(self):
        vocab = set()
        for state, counter in self.chain.items():
            vocab.update(state)
            vocab.update(counter.keys())
        for state in self.starts:
            vocab.update(state)
        return len(vocab)

    def to_dict(self):
        sep = "\x1f"
        return {
            "order": self.order,
            "chain": {
                sep.join(state): dict(counter)
                for state, counter in self.chain.items()
            },
            "starts": {sep.join(state): count for state, count in self.starts.items()},
        }

    @classmethod
    def from_dict(cls, data):
        sep = "\x1f"
        model = cls(order=data["order"])
        for key, counts in data["chain"].items():
            model.chain[tuple(key.split(sep))] = Counter(counts)
        for key, count in data["starts"].items():
            model.starts[tuple(key.split(sep))] = count
        return model
