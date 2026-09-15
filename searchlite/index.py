import math
import re
from collections import Counter, defaultdict

from searchlite.tokenize import tokenize


class Index:
    """An in-memory inverted index with TF-IDF ranking."""

    def __init__(self):
        self.postings = {}      # term -> {doc_id: term_freq}
        self.positions = {}     # term -> {doc_id: [token positions]}
        self.doc_lengths = {}   # doc_id -> token count
        self.doc_titles = {}    # doc_id -> short preview text
        self.doc_texts = {}     # doc_id -> full text, for snippet generation

    @property
    def doc_count(self):
        return len(self.doc_lengths)

    def add_document(self, doc_id, text):
        if doc_id in self.doc_lengths:
            self.remove_document(doc_id)
        tokens = tokenize(text)
        counts = Counter(tokens)
        for term, freq in counts.items():
            self.postings.setdefault(term, {})[doc_id] = freq
        term_positions = defaultdict(list)
        for i, term in enumerate(tokens):
            term_positions[term].append(i)
        for term, positions in term_positions.items():
            self.positions.setdefault(term, {})[doc_id] = positions
        self.doc_lengths[doc_id] = len(tokens)
        preview = text.strip().replace("\n", " ")
        self.doc_titles[doc_id] = preview[:200]
        self.doc_texts[doc_id] = text

    def remove_document(self, doc_id):
        if doc_id not in self.doc_lengths:
            return False
        for term in list(self.postings.keys()):
            postings = self.postings[term]
            if doc_id in postings:
                del postings[doc_id]
                if not postings:
                    del self.postings[term]
        for term in list(self.positions.keys()):
            positions = self.positions[term]
            if doc_id in positions:
                del positions[doc_id]
                if not positions:
                    del self.positions[term]
        del self.doc_lengths[doc_id]
        del self.doc_titles[doc_id]
        self.doc_texts.pop(doc_id, None)
        return True

    def search_phrase(self, phrase, top_k=10):
        """Find documents containing the exact sequence of query terms
        (after tokenization/stopword-filtering, same as ranked search), in
        the order given. Ranked by number of phrase occurrences per
        document. Requires a positional index built by add_document — an
        index loaded from an older save file with no positions data will
        find no matches even for terms that are otherwise indexed.
        """
        terms = tokenize(phrase)
        if not terms:
            return []
        if len(terms) == 1:
            postings = self.postings.get(terms[0], {})
            ranked = sorted(postings.items(), key=lambda kv: (-kv[1], kv[0]))
            return ranked[:top_k]
        term_positions = [self.positions.get(term, {}) for term in terms]
        if any(not tp for tp in term_positions):
            return []
        candidate_docs = set(term_positions[0].keys())
        for tp in term_positions[1:]:
            candidate_docs &= set(tp.keys())
        matches = {}
        for doc_id in candidate_docs:
            offset_sets = [set(tp[doc_id]) for tp in term_positions[1:]]
            count = 0
            for start in term_positions[0][doc_id]:
                if all((start + i + 1) in offsets for i, offsets in enumerate(offset_sets)):
                    count += 1
            if count:
                matches[doc_id] = count
        ranked = sorted(matches.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:top_k]

    def search(self, query, top_k=10, rank="tfidf"):
        if rank == "bm25":
            scores = self._score_bm25(query)
        elif rank == "tfidf":
            scores = self._score_tfidf(query)
        else:
            raise ValueError(f"unknown rank method {rank!r} (expected 'tfidf' or 'bm25')")
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:top_k]

    def _score_tfidf(self, query):
        tokens = tokenize(query)
        scores = defaultdict(float)
        n = self.doc_count
        for term in tokens:
            postings = self.postings.get(term)
            if not postings:
                continue
            idf = math.log((n + 1) / (len(postings) + 1)) + 1
            for doc_id, tf in postings.items():
                scores[doc_id] += tf * idf
        return scores

    def _score_bm25(self, query, k1=1.5, b=0.75):
        tokens = tokenize(query)
        scores = defaultdict(float)
        n = self.doc_count
        if n == 0:
            return scores
        avg_doc_len = sum(self.doc_lengths.values()) / n
        for term in tokens:
            postings = self.postings.get(term)
            if not postings:
                continue
            idf = math.log((n - len(postings) + 0.5) / (len(postings) + 0.5) + 1)
            for doc_id, tf in postings.items():
                doc_len = self.doc_lengths.get(doc_id, 0)
                denom = tf + k1 * (1 - b + b * doc_len / avg_doc_len)
                scores[doc_id] += idf * (tf * (k1 + 1)) / denom
        return scores

    def snippet(self, doc_id, query, radius=40):
        """Return a short excerpt of doc_id's text around the first query
        term match, with matched terms wrapped in **asterisks**. Falls back
        to a plain leading excerpt if no query term is found in the text
        (e.g. a stopword-only query, or an older index with no stored text).
        """
        text = self.doc_texts.get(doc_id)
        if text is None:
            return self.doc_titles.get(doc_id, "")
        terms = tokenize(query)
        if not terms:
            return text.strip().replace("\n", " ")[:2 * radius]
        term_re = re.compile(
            r"\b(" + "|".join(re.escape(t) for t in terms) + r")\b",
            re.IGNORECASE,
        )
        match = term_re.search(text)
        if not match:
            return text.strip().replace("\n", " ")[:2 * radius]
        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        excerpt = text[start:end].replace("\n", " ")
        excerpt = term_re.sub(lambda m: f"**{m.group(0)}**", excerpt)
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(text):
            excerpt = excerpt + "..."
        return excerpt

    def to_dict(self):
        return {
            "postings": self.postings,
            "positions": self.positions,
            "doc_lengths": self.doc_lengths,
            "doc_titles": self.doc_titles,
            "doc_texts": self.doc_texts,
        }

    @classmethod
    def from_dict(cls, data):
        index = cls()
        index.postings = {
            term: dict(docs) for term, docs in data.get("postings", {}).items()
        }
        index.positions = {
            term: {doc_id: list(positions) for doc_id, positions in docs.items()}
            for term, docs in data.get("positions", {}).items()
        }
        index.doc_lengths = dict(data.get("doc_lengths", {}))
        index.doc_titles = dict(data.get("doc_titles", {}))
        index.doc_texts = dict(data.get("doc_texts", {}))
        return index
