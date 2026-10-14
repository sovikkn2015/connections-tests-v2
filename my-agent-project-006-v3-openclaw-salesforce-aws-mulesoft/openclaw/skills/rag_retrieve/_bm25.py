"""BM25 lexical retriever.

Wraps `rank_bm25` when installed; falls back to a deterministic pure-Python
BM25 implementation when it's not. Why BM25 alongside dense retrieval:
tickers ("GS"), CUSIPs, exact numerical phrases break pure-semantic retrieval.
"""

from __future__ import annotations

import math
import re
from typing import Iterable, List, Sequence, Tuple

try:
    from rank_bm25 import BM25Okapi  # type: ignore
    _HAS_RANKBM25 = True
except ImportError:  # pragma: no cover
    _HAS_RANKBM25 = False


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def tokenize(text: str) -> List[str]:
    """Lowercased alpha-num tokens. Same rule for corpus and queries."""
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


class _FallbackBM25:
    """Pure-Python Okapi BM25. k1=1.5, b=0.75 (library defaults)."""

    def __init__(
        self,
        corpus_tokens: Sequence[Sequence[str]],
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = [list(t) for t in corpus_tokens]
        self.doc_lens = [len(d) for d in self.corpus]
        self.avgdl = sum(self.doc_lens) / len(self.doc_lens) if self.doc_lens else 0
        self.doc_count = len(self.corpus)

        df: dict[str, int] = {}
        for doc in self.corpus:
            for term in set(doc):
                df[term] = df.get(term, 0) + 1
        self.df = df

    def _idf(self, term: str) -> float:
        n = self.df.get(term, 0)
        return math.log(1 + (self.doc_count - n + 0.5) / (n + 0.5))

    def get_scores(self, query: Sequence[str]) -> List[float]:
        scores: List[float] = []
        q_terms = list(query)
        for i, doc in enumerate(self.corpus):
            dl = self.doc_lens[i]
            if dl == 0 or self.avgdl == 0:
                scores.append(0.0)
                continue
            score = 0.0
            for term in q_terms:
                if term not in self.df:
                    continue
                tf = doc.count(term)
                if tf == 0:
                    continue
                idf = self._idf(term)
                numer = tf * (self.k1 + 1)
                denom = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                score += idf * (numer / denom)
            scores.append(score)
        return scores


class BM25Retriever:
    """Corpus + scoring adapter used by rag_retrieve."""

    def __init__(self, documents: Iterable[str]) -> None:
        self.documents = list(documents)
        self.tokens = [tokenize(d) for d in self.documents]
        if _HAS_RANKBM25:
            self._impl: object = BM25Okapi(self.tokens)
        else:
            self._impl = _FallbackBM25(self.tokens)

    def top_k(self, query: str, k: int = 30) -> List[Tuple[int, float]]:
        """Return top-k (doc_index, score) tuples, score-descending."""
        q_tokens = tokenize(query)
        scores = self._impl.get_scores(q_tokens)  # type: ignore[attr-defined]
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return ranked[:k]

    @property
    def using_rank_bm25(self) -> bool:
        return _HAS_RANKBM25
