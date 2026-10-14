"""Cohere Rerank 3.5 wrapper + deterministic stub.

The real reranker is a cross-encoder served by Cohere. For tests we use a
`StubReranker` whose order is deterministic. Production injects `CohereReranker`.
"""

from __future__ import annotations

import os
from typing import List, Protocol, Sequence, Tuple


class Reranker(Protocol):
    async def rerank(
        self, query: str, documents: Sequence[str], top_n: int = 5
    ) -> List[Tuple[int, float]]:
        ...


class StubReranker:
    """Deterministic reranker: preserves incoming order but surfaces docs
    that share the most query words at the top (Jaccard - length penalty).

    Not a real cross-encoder — sufficient for wiring-correctness tests.
    """

    async def rerank(
        self, query: str, documents: Sequence[str], top_n: int = 5
    ) -> List[Tuple[int, float]]:
        q_terms = set((query or "").lower().split())
        scored: List[Tuple[int, float]] = []
        for i, doc in enumerate(documents):
            d_terms = set((doc or "").lower().split())
            if not q_terms or not d_terms:
                scored.append((i, 0.0))
                continue
            inter = len(q_terms & d_terms)
            union = len(q_terms | d_terms)
            jaccard = inter / union if union else 0.0
            length_penalty = min(0.2, len(doc) / 5000)
            scored.append((i, jaccard - length_penalty))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]


class CohereReranker:  # pragma: no cover - real-transport
    """Real Cohere Rerank 3.5 client. Not exercised in unit tests."""

    def __init__(self, *, model: str = "rerank-3.5") -> None:
        self._model = model
        self._api_key = os.getenv("COHERE_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "COHERE_API_KEY required for CohereReranker; seed via Secrets Manager"
            )

    async def rerank(
        self, query: str, documents: Sequence[str], top_n: int = 5
    ) -> List[Tuple[int, float]]:
        try:
            import httpx  # type: ignore
        except ImportError as exc:
            raise RuntimeError("httpx required for CohereReranker") from exc

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.cohere.com/v1/rerank",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "query": query,
                    "documents": list(documents),
                    "top_n": top_n,
                },
            )
            resp.raise_for_status()
            body = resp.json()
            out: List[Tuple[int, float]] = []
            for item in body.get("results", [])[:top_n]:
                out.append((int(item["index"]), float(item["relevance_score"])))
            return out
