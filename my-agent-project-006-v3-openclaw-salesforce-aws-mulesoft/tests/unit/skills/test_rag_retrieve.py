"""Tests for rag_retrieve skill — BM25 + dense + structural + rerank."""

from __future__ import annotations

import pytest

from openclaw.skills.rag_retrieve import (
    Corpus,
    CorpusDocument,
    RAGInput,
    run,
)


_SAMPLE_FILINGS = [
    CorpusDocument(
        source_chunk_id="f1",
        source_url="https://edgar/NVDA-10Q-1a",
        section="item_1a_risk_factors",
        text=(
            "NVDA risk factors include supply-chain dependency on TSMC and "
            "export controls on advanced chips to China."
        ),
    ),
    CorpusDocument(
        source_chunk_id="f2",
        source_url="https://edgar/NVDA-10Q-7",
        section="item_7_mda",
        text=(
            "Management discussion and analysis: data center revenue grew "
            "120% YoY driven by hyperscaler demand."
        ),
    ),
    CorpusDocument(
        source_chunk_id="f3",
        source_url="https://edgar/NVDA-10Q-8",
        section="item_8_financial_statements",
        text="Net income was $18.8 billion for the quarter ended 2026-01-28.",
    ),
    CorpusDocument(
        source_chunk_id="f4",
        source_url="https://edgar/NVDA-10Q-1",
        section="item_1_business",
        text="NVIDIA is a computing infrastructure company.",
    ),
]


@pytest.mark.asyncio
async def test_rag_returns_k_chunks(mock_mcp) -> None:
    out = await run(
        RAGInput(
            query="risk factors for NVDA supply chain",
            corpus=Corpus.FILINGS,
            k=2,
            corpus_documents=_SAMPLE_FILINGS,
            principal_id="u",
            session_id="s",
            correlation_id="c",
        )
    )
    assert len(out.chunks) == 2
    assert out.used_rerank is True
    assert out.retriever_counts["structural"] > 0


@pytest.mark.asyncio
async def test_rag_structural_surfaces_risk_section(mock_mcp) -> None:
    out = await run(
        RAGInput(
            query="risk factors",
            corpus=Corpus.FILINGS,
            k=3,
            corpus_documents=_SAMPLE_FILINGS,
            principal_id="u",
            session_id="s",
            correlation_id="c",
        )
    )
    ids = [c.source_chunk_id for c in out.chunks]
    assert "f1" in ids


@pytest.mark.asyncio
async def test_rag_research_corpus_skips_structural(mock_mcp) -> None:
    out = await run(
        RAGInput(
            query="data center growth",
            corpus=Corpus.RESEARCH,
            k=2,
            corpus_documents=_SAMPLE_FILINGS,
            principal_id="u",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.retriever_counts["structural"] == 0


@pytest.mark.asyncio
async def test_rag_chunks_carry_citations(mock_mcp) -> None:
    out = await run(
        RAGInput(
            query="NVDA",
            corpus=Corpus.FILINGS,
            k=4,
            corpus_documents=_SAMPLE_FILINGS,
            principal_id="u",
            session_id="s",
            correlation_id="c",
        )
    )
    assert all(c.source_chunk_id for c in out.chunks)
    assert all(c.source_url for c in out.chunks)
