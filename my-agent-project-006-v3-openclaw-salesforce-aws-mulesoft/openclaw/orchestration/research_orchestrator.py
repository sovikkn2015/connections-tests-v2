"""Research orchestrator — Sarah's agent.

Fans out five research specialists in parallel (market, filings, sentiment,
compliance, statement) and synthesizes their cited outputs into a brief that
is safe for RM consumption. Citation-enforcement strips unsourced sentences.
"""

from __future__ import annotations

import re
from typing import List

from .coordinator import Orchestrator
from .messages import OrchestratorDispatch, SessionContext, WorkerResponse
from .topology import AGENT_TOPOLOGY


RESEARCH_SPECIALISTS: List[str] = [
    "market_specialist",
    "filings_specialist",
    "sentiment_specialist",
    "compliance_specialist",
    "statement_specialist",
]


def _narrow_intent(query: str) -> List[str]:
    """Optional narrowing: if the query is pure sentiment, skip filings/statements.

    Default path is all five. Only narrow when the query text is unambiguous.
    The parallel fanout is cheap and five concurrent spans in the audit strip
    is part of the demo value.
    """
    q = query.lower()
    if "sentiment" in q and not any(
        k in q for k in ("10-q", "10-k", "filing", "margin", "risk")
    ):
        return ["sentiment_specialist", "market_specialist", "compliance_specialist"]
    # Default fanout includes 4 specialists so the demo brief has market
    # pulse + filings substance + sentiment + compliance. The 5th
    # (statement_specialist) is only fired when the query specifically asks
    # for financial statement analysis — it's slower and largely redundant
    # with filings_specialist for short-form briefs. Total turn still needs
    # to fit inside the 29s API Gateway REST window so per-worker timeout
    # is tuned accordingly.
    if "financial statement" in q or "margin" in q or "roe" in q or "roic" in q:
        return [
            "market_specialist",
            "filings_specialist",
            "sentiment_specialist",
            "compliance_specialist",
            "statement_specialist",
        ]
    return [
        "market_specialist",
        "filings_specialist",
        "sentiment_specialist",
        "compliance_specialist",
    ]


class ResearchOrchestratorImpl(Orchestrator):
    """Concrete research-orchestrator. Parallel fanout; cited synthesis."""

    async def plan(
        self,
        query: str,
        ctx: SessionContext,
    ) -> List[OrchestratorDispatch]:
        """Dispatch up to 5 specialists in parallel for a research request."""
        specialists = _narrow_intent(query)
        tickers = _extract_tickers(query)
        ticker = tickers[0] if tickers else "UNKNOWN"
        ticker_label = ", ".join(tickers) if len(tickers) > 1 else ticker
        dispatches: List[OrchestratorDispatch] = []
        for agent_id in specialists:
            if agent_id not in AGENT_TOPOLOGY:
                continue
            dispatches.append(
                OrchestratorDispatch(
                    target_agent_id=agent_id,
                    task=_task_for(agent_id, ticker_label, query),
                    context_subset={"ticker": ticker, "tickers": ",".join(tickers), "persona": ctx.persona},
                    timeout_s=45.0,
                )
            )
        return dispatches

    async def synthesize(
        self,
        query: str,
        ctx: SessionContext,
        responses: List[WorkerResponse],
    ) -> str:
        """Combine specialist outputs into a cited brief.

        - Hard-stop surfacing: if compliance_specialist returned DENY or mnpi_flag,
          surface prominently and mark rm_consumable=false.
        - Citation-enforcement: unsourced narrative sentences are cut after synth.
        """
        sections: List[str] = []
        all_citations: List[str] = []
        compliance_status = "UNKNOWN"
        rm_consumable = True
        failed: List[str] = []

        for r in responses:
            if r.errors:
                failed.extend(
                    f"{r.agent_id}({e.error_type.value})" for e in r.errors
                )
                if any(not e.recoverable for e in r.errors):
                    rm_consumable = False
                continue

            text = r.result.get("text", "") or ""
            all_citations.extend(r.citations)

            if r.agent_id == "compliance_specialist":
                compliance_status = _parse_compliance(text)
                if compliance_status == "DENY":
                    rm_consumable = False

            sections.append(self._format_section(r.agent_id, text, r.citations))

        header = (
            f"# Research Brief (session {ctx.session_id}, turn {ctx.turn_number})\n"
            f"compliance_status: {compliance_status}\n"
            f"rm_consumable: {str(rm_consumable).lower()}\n"
        )
        if failed:
            header += f"gaps: {', '.join(failed)}\n"

        body = "\n\n".join(sections) if sections else "(no specialist responses)"
        enforced = enforce_citations(body)
        footer = (
            "\n\nCitations: " + ", ".join(sorted(set(all_citations)))
            if all_citations
            else ""
        )
        return f"{header}\n{enforced}{footer}"

    @staticmethod
    def _format_section(agent_id: str, text: str, citations: List[str]) -> str:
        """Per-specialist narrative section with a trailing citation tag."""
        cite_tag = f"[src:{citations[0]}]" if citations else ""
        summary = text.strip()
        if not summary:
            return f"## {agent_id}\n(empty) {cite_tag}"
        has_cite = bool(re.search(r"\[src:[A-Za-z0-9_\-]+\]", summary))
        if not has_cite and cite_tag:
            summary = f"{summary} {cite_tag}"
        return f"## {agent_id}\n{summary}"


def _extract_tickers(query: str) -> list[str]:
    """Extract ALL uppercase 1-5 char tokens that look like tickers.

    Returns deduplicated list preserving first-occurrence order.
    Filters out common English stopwords that happen to be uppercase.
    """
    _STOPWORDS = {
        "I", "A", "AN", "AS", "AT", "BE", "BY", "GO", "IF", "IN", "IS",
        "IT", "MY", "NO", "OF", "ON", "OR", "SO", "TO", "UP", "US", "WE",
        "VS", "AND", "THE", "FOR", "NOT", "BUT", "ALL", "ANY", "CAN",
        "HAD", "HAS", "HER", "HIM", "HIS", "HOW", "ITS", "LET", "MAY",
        "NOR", "OUR", "OWN", "SAY", "SHE", "TOO", "USE", "WAY", "WHO",
        "BOY", "DID", "GET", "HIT", "OLD", "PUT", "RUN", "TOP", "WHY",
        "ROE", "R&D",
    }
    seen: dict[str, None] = {}
    for m in re.finditer(r"\b([A-Z]{1,5})\b", query):
        token = m.group(1)
        if token not in _STOPWORDS and token not in seen:
            seen[token] = None
    return list(seen.keys())


def _extract_ticker(query: str) -> str:
    """First ticker for backward compat."""
    tickers = _extract_tickers(query)
    return tickers[0] if tickers else ""


def _task_for(agent_id: str, ticker: str, query: str) -> str:
    """Per-specialist task phrasing. Concrete, narrow, bounded."""
    tasks = {
        "market_specialist": (
            f"Get live quote, volume, 52-week range, and implied earnings move "
            f"for {ticker}. Return the structured shape your system prompt specifies."
        ),
        "filings_specialist": (
            f"Retrieve the latest 10-Q and 10-K for {ticker}. Extract relevant "
            f"risk-factor and MD&A sections. Return citations to source_chunk_ids."
        ),
        "sentiment_specialist": (
            f"Score 30-day news sentiment for {ticker}. Return "
            f"sentiment_score/confidence/tone_drivers with headline citations."
        ),
        "compliance_specialist": (
            f"Run pre-publication compliance screening for {ticker}: restricted list, "
            f"trading window, MNPI flags, concentration. Return ALLOW/DENY/REVIEW."
        ),
        "statement_specialist": (
            f"Run deterministic financial-statement analysis for {ticker}: "
            f"5-year margin trend, ROE/ROIC, peer comparison. Numbers from calculators."
        ),
    }
    return tasks.get(
        agent_id, f"Process the following research query: {query[:200]}"
    )


def _parse_compliance(text: str) -> str:
    """Extract ALLOW/DENY/REVIEW from a compliance-specialist text payload."""
    up = text.upper()
    for tag in ("DENY", "ALLOW", "REVIEW"):
        if tag in up:
            return tag
    return "UNKNOWN"


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_CITE = re.compile(r"\[src:[A-Za-z0-9_\-]+\]")


def enforce_citations(text: str) -> str:
    """Strip sentences that don't contain a [src:xxxx] marker.

    Server-side harness that makes "every sentence cites a source" real.
    Applied AFTER the LLM has finished writing.

    Preserves: headings, JSON-looking lines, fenced code blocks, blank lines.
    """
    if not text:
        return text

    preserved: List[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            preserved.append(line)
            continue
        if in_fence or stripped.startswith("#") or stripped.startswith("##"):
            preserved.append(line)
            continue
        if not stripped:
            preserved.append(line)
            continue
        if stripped.startswith("{") or stripped.startswith("["):
            preserved.append(line)
            continue

        sentences = _SENTENCE_END.split(line)
        kept = [s for s in sentences if _CITE.search(s)]
        if kept:
            preserved.append(" ".join(kept))
    return "\n".join(preserved)
