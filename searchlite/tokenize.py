import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were",
    "be", "been", "being", "of", "to", "in", "on", "for", "with",
    "as", "by", "at", "it", "this", "that", "from", "not",
})


def tokenize(text, stopwords=True):
    words = _TOKEN_RE.findall(text.lower())
    if stopwords:
        words = [w for w in words if w not in _STOPWORDS]
    return words
