"""rag_retrieve.run — hybrid retrieval + rerank. NO generation.

V3 depth layer 1 — 2026 RAG discipline:

  1. BM25 lexical retriever        (_bm25.py)
  2. Bedrock Titan v2 dense vector (_dense.py)
  3. Section-aware structural      (_structural.py) — filings only
  4. Cohere Rerank 3.5             (_rerank.py)

Fusion: reciprocal-rank fusion of BM25 + dense + structural -> top 30,
then Cohere Rerank -> top K (default 5). Generation happens in the
orchestrator with a citation-enforcement harness (src:xxxx markers).

Two corpora:
  - "filings"  — SEC 10-K/10-Q/8-K; structural retriever ACTIVE
  - "research" — research brief library; structural retriever SKIPPED
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client
from ._bm25 import BM25Retriever
from ._dense import DenseRetriever, Embedder, StubEmbedder
from ._rerank import Reranker, StubReranker
from ._structural import StructuralRetriever


class Corpus(str, Enum):
    FILINGS = "filings"
    RESEARCH = "research"


class Chunk(BaseModel):
    """A retrieved chunk. Each carries source_chunk_id for citation."""

    source_chunk_id: str = Field(..., min_length=1)
    source_url: Optional[str] = None
    section: Optional[str] = None
    score: float
    text: str
    model_config = {"frozen": True}


class CorpusDocument(BaseModel):
    """A single document indexed into a corpus."""

    source_chunk_id: str
    source_url: Optional[str] = None
    section: Optional[str] = None
    text: str
    model_config = {"frozen": True}


class RAGInput(BaseModel):
    """Retrieval request. `corpus_documents` is injected by the caller for
    unit-test determinism; production wires a corpus loader upstream that
    returns the principal-scoped document set."""

    query: str = Field(..., min_length=1)
    corpus: Corpus
    k: int = Field(5, ge=1, le=20)
    rrf_top_n: int = Field(30, ge=5, le=200, description="RRF fusion top-n")

    corpus_documents: List[CorpusDocument] = Field(..., min_length=1)

    principal_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)

    model_config = {"frozen": True}


class RAGOutput(BaseModel):
    chunks: List[Chunk]
    used_rerank: bool
    retriever_counts: Dict[str, int] = Field(default_factory=dict)
    audit_row_id: str
    model_config = {"frozen": True}


class _CorpusIndex:
    """Holds the three built retrievers for a single corpus."""

    def __init__(
        self,
        documents: Sequence[CorpusDocument],
        *,
        use_structural: bool,
        embedder: Embedder,
    ) -> None:
        self.documents = list(documents)
        texts = [d.text for d in documents]
        self.bm25 = BM25Retriever(texts)
        self.dense = DenseRetriever(texts, embedder=embedder)
        self.structural: Optional[StructuralRetriever] = None
        if use_structural:
            sections = [d.section or "unknown" for d in documents]
            self.structural = StructuralRetriever(sections, texts)


def _rrf_fuse(
    ranked_lists: List[List[Tuple[int, float]]], *, k: int = 60
) -> List[Tuple[int, float]]:
    """Reciprocal Rank Fusion.

    Fused score = sum over lists of 1 / (k + rank_in_list). k=60 is the
    canonical value. Returns (doc_index, fused_score), score-descending.
    """
    fused: Dict[int, float] = {}
    for lst in ranked_lists:
        for rank, (idx, _score) in enumerate(lst):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(fused.items(), key=lambda x: x[1], reverse=True)


async def run(
    payload: RAGInput,
    *,
    mcp: Optional[MCPClient] = None,
    embedder: Optional[Embedder] = None,
    reranker: Optional[Reranker] = None,
) -> RAGOutput:
    """Hybrid retrieval + rerank. No generation."""
    client = mcp or get_shared_mock_client()
    emb: Embedder = embedder or StubEmbedder()
    rerank: Reranker = reranker or StubReranker()

    use_structural = payload.corpus is Corpus.FILINGS
    index = _CorpusIndex(
        payload.corpus_documents, use_structural=use_structural, embedder=emb
    )

    bm25_hits = index.bm25.top_k(payload.query, k=payload.rrf_top_n)
    dense_hits = await index.dense.top_k(payload.query, k=payload.rrf_top_n)
    structural_hits: List[Tuple[int, float]] = []
    if index.structural is not None:
        structural_hits = index.structural.top_k(payload.query, k=payload.rrf_top_n)

    lists_to_fuse = [bm25_hits, dense_hits]
    if structural_hits:
        lists_to_fuse.append(structural_hits)
    fused = _rrf_fuse(lists_to_fuse)

    candidate_indices = [idx for idx, _ in fused[: payload.rrf_top_n]]
    candidate_docs = [payload.corpus_documents[i].text for i in candidate_indices]

    reranked = await rerank.rerank(payload.query, candidate_docs, top_n=payload.k)

    chunks: List[Chunk] = []
    for local_idx, score in reranked:
        doc = payload.corpus_documents[candidate_indices[local_idx]]
        chunks.append(
            Chunk(
                source_chunk_id=doc.source_chunk_id,
                source_url=doc.source_url,
                section=doc.section,
                score=round(float(score), 4),
                text=doc.text,
            )
        )

    audit = await audit_run(
        AuditInput(
            action=AuditAction.ADVISORY_QUERY,
            principal_id=payload.principal_id,
            agent_id="rag_retrieve",
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            gate_trace=[
                {"gate": "rag_fusion", "corpus": payload.corpus.value,
                 "bm25": len(bm25_hits), "dense": len(dense_hits),
                 "structural": len(structural_hits), "reranked": len(chunks)}
            ],
            payload={
                "query_len": len(payload.query),
                "k": payload.k,
                "corpus": payload.corpus.value,
                "source_chunk_ids": [c.source_chunk_id for c in chunks],
            },
        ),
        mcp=client,
    )

    return RAGOutput(
        chunks=chunks,
        used_rerank=True,
        retriever_counts={
            "bm25": len(bm25_hits),
            "dense": len(dense_hits),
            "structural": len(structural_hits),
            "fused": len(fused),
        },
        audit_row_id=audit.audit_row_id,
    )
