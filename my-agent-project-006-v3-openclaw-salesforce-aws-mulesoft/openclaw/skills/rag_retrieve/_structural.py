"""Section-aware structural retrieval for SEC filings.

Parsed 10-K / 10-Q carry canonical section labels (item_1_business,
item_1a_risk_factors, item_7_mda, item_8_financial_statements, etc).

Structural retrieval boosts chunks whose `section` label matches keywords
present in the query. Catches cases BM25 misses because the *section* is
the signal, not the body words.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple


# Keyword -> section mappings. Keys are lower-cased substrings.
_KEYWORD_TO_SECTION: Dict[str, List[str]] = {
    "risk factor": ["item_1a_risk_factors"],
    "risk factors": ["item_1a_risk_factors"],
    "mda": ["item_7_mda"],
    "md&a": ["item_7_mda"],
    "management discussion": ["item_7_mda"],
    "quant risk": ["item_7a_quant_risk"],
    "market risk": ["item_7a_quant_risk"],
    "financial statements": ["item_8_financial_statements"],
    "balance sheet": ["item_8_financial_statements"],
    "income statement": ["item_8_financial_statements"],
    "cash flow": ["item_8_financial_statements"],
    "business": ["item_1_business"],
    "properties": ["item_2_properties"],
    "legal proceedings": ["item_3_legal_proceedings"],
    "directors": ["item_10_directors"],
    "governance": ["item_10_directors"],
}


def _section_affinity(query: str, section: str) -> float:
    """Return a bonus score when the query implicates this section."""
    q = (query or "").lower()
    for kw, sections in _KEYWORD_TO_SECTION.items():
        if kw in q and section in sections:
            return 1.5
    return 0.0


class StructuralRetriever:
    """Per-document section-aware scorer. Used alongside BM25 and dense."""

    def __init__(self, sections: Sequence[str], documents: Sequence[str]) -> None:
        if len(sections) != len(documents):
            raise ValueError("sections and documents must be same length")
        self.sections = list(sections)
        self.documents = list(documents)

    def top_k(self, query: str, k: int = 30) -> List[Tuple[int, float]]:
        q_terms = set((query or "").lower().split())
        scored: List[Tuple[int, float]] = []
        for i, section in enumerate(self.sections):
            base = _section_affinity(query, section)
            doc_lower = self.documents[i].lower()
            term_hits = sum(1 for t in q_terms if t in doc_lower)
            length_prior = min(0.25, len(self.documents[i]) / 50_000)
            score = base + 0.1 * term_hits + length_prior
            if score > 0:
                scored.append((i, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]
