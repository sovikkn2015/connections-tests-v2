"""Liaison orchestrator — the client-facing agent.

Decides FAQ (Haiku) vs escalation (Sonnet context-specialist + rm-handoff).
Read-only persona. Every response carries a disclaimer and "your RM" CTA.
MNPI scrubbing enforced upstream by trust layer; a final tripwire here
redacts any leaked dollar amount or share count before emit.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import List

from .coordinator import Orchestrator
from .messages import OrchestratorDispatch, SessionContext, WorkerResponse
from ..skills.rm_handoff.actions import RmHandoffInput, run as rm_handoff_run


class LiaisonDecision(str, Enum):
    """Two decisions the liaison orchestrator makes."""

    FAQ = "faq"
    ESCALATE = "escalate"


_ESCALATION_HINTS = re.compile(
    r"\b(buy|sell|should i|position|concentration|my\s+\w+\s+in\s+[A-Z]{1,5}|"
    r"trim|[A-Z]{2,5}\s+(is|going|up|down)|worried|crashing|earnings)\b",
    re.IGNORECASE,
)
_FAQ_HINTS = re.compile(
    r"\b(market\s+hours?|what\s+(is|are)\s+a?\s?(10-?[kq]|etf|index|portfolio|filing)|"
    r"schedule|call\s+my\s+rm|appointment|office\s+hours|"
    r"when\s+is\s+earnings|earnings\s+season|what\s+is\s+a\s+\w+\s+filing)\b",
    re.IGNORECASE,
)


def classify_inquiry(query: str) -> LiaisonDecision:
    """FAQ if pure-informational; ESCALATE otherwise.

    Err on the side of ESCALATE. Losing a chat turn by adding a human is
    cheap; giving a wrong FAQ on a ticker question is a compliance problem.

    Priority: check FAQ FIRST — if the query matches a known FAQ pattern,
    answer it directly. Only escalate if it doesn't match FAQ and DOES
    match an escalation trigger. This prevents benign questions like
    "When is earnings season?" from being escalated just because they
    contain the word "earnings".
    """
    if _FAQ_HINTS.search(query):
        return LiaisonDecision.FAQ
    if _ESCALATION_HINTS.search(query):
        return LiaisonDecision.ESCALATE
    return LiaisonDecision.ESCALATE


_DISCLAIMER = "For informational purposes. Your RM makes recommendations."


class LiaisonOrchestratorImpl(Orchestrator):
    """Concrete liaison-orchestrator. FAQ via Haiku; escalation via Sonnet."""

    async def plan(
        self,
        query: str,
        ctx: SessionContext,
    ) -> List[OrchestratorDispatch]:
        """One specialist per turn — single-agent dispatch, no fanout."""
        decision = classify_inquiry(query)
        if decision is LiaisonDecision.FAQ:
            return [
                OrchestratorDispatch(
                    target_agent_id="faq_specialist",
                    task=(
                        f"Answer as a bounded FAQ only. Always end with a "
                        f"\"Your RM\" CTA and the standard disclaimer.\n\n"
                        f"Question: {query}"
                    ),
                    context_subset={"channel": ctx.correlation_id[:8]},
                    timeout_s=15.0,
                )
            ]
        # Escalation: the rm_handoff skill in synthesize() does the real
        # work (writes Client_Inquiry__c, optionally Research_Request__c,
        # audit row). The context_specialist was dispatched here to read
        # MNPI-filtered client context, but it consistently times out
        # (~21s) because the CRM tools are slow under OBO. For escalation,
        # the client doesn't need their own context read back — they need
        # an acknowledgement and a handoff. Skip the specialist; let
        # synthesize() handle it directly.
        return []

    async def synthesize(
        self,
        query: str,
        ctx: SessionContext,
        responses: List[WorkerResponse],
    ) -> str:
        """Produce client-safe output with disclaimer + CTA.

        For ESCALATE decisions, also writes Client_Inquiry__c + optional
        Research_Request__c + audit row via rm_handoff. Narrative 2 loop
        closer: the RM actually sees the inquiry in their queue.
        """
        decision = classify_inquiry(query)

        # FAQ path: no SObject writes.
        if decision is LiaisonDecision.FAQ:
            if not responses or responses[0].errors:
                return (
                    "Let me get you an answer. For informational purposes.\n"
                    f"{_DISCLAIMER}"
                )
            r = responses[0]
            text = r.result.get("text", "") or ""
            if _DISCLAIMER not in text:
                text = f"{text.strip()}\n{_DISCLAIMER}"
            return _mnpi_tripwire(text)

        # ESCALATE path: call rm_handoff to write Client_Inquiry__c and
        # optionally Research_Request__c. Failures are degraded-mode so
        # the client still gets a clean acknowledgement even if Salesforce
        # is blipping.
        ticker = _extract_ticker(query)
        research_needed = ticker is not None
        cinq = "pending"
        rreq = None
        try:
            handoff = await rm_handoff_run(
                RmHandoffInput(
                    inquiry_text=query,
                    client_contact_id=getattr(ctx, "client_contact_id", "")
                    or ctx.principal_id,
                    rm_user_id="",
                    inquiry_type="question",
                    channel="web",
                    ticker=ticker,
                    research_needed=research_needed,
                    priority="Normal",
                    principal_id=ctx.principal_id,
                    session_id=ctx.session_id,
                    correlation_id=ctx.correlation_id,
                    agent_id="liaison_orchestrator",
                ),
            )
            cinq = handoff.client_inquiry_id
            rreq = handoff.research_request_id
        except Exception as exc:  # noqa: BLE001 - never fail the user-facing turn
            import logging as _lg
            _lg.getLogger(__name__).warning("rm_handoff_degraded %s", exc)
            cinq = "pending"
            rreq = None

        # Stash queue_updates on the first response's result dict so
        # agentcore_server can lift them to the envelope top level.
        # This closes N2: RM Marcus sees the client's inquiry appear
        # in his Actions queue as a new unread high-priority item in
        # real time, not just in the conversation body.
        queue_updates: List[dict] = []
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        queue_updates.append({
            "queue": "alerts",
            "op": "add",
            "item": {
                "id": cinq,
                "kind": "alerts",
                "title": f"{_extract_ticker(query) or 'Client'}: {query[:60]}",
                "subtitle": "Client inquiry via liaison — needs RM review",
                "badge": "high" if (research_needed or "earnings" in query.lower()) else "med",
                "timestamp": now_iso,
                "unread": True,
                "client_contact_id": getattr(ctx, "client_contact_id", "")
                or ctx.principal_id,
            },
        })
        if rreq:
            queue_updates.append({
                "queue": "briefs",
                "op": "add",
                "item": {
                    "id": rreq,
                    "kind": "briefs",
                    "title": f"Research ask: {ticker}",
                    "subtitle": f"Queued from client inquiry {cinq[:12]}",
                    "badge": "med",
                    "timestamp": now_iso,
                    "unread": True,
                },
            })
        # Attach to the first response if present so the harvester in
        # agentcore_server picks it up without adding a new plumbing field.
        if responses:
            r0 = responses[0]
            if hasattr(r0, "result") and isinstance(r0.result, dict):
                r0.result["queue_updates"] = queue_updates
            else:
                # WorkerResponse is frozen pydantic — if result is None,
                # substitute a dict-bearing result. This shouldn't happen
                # on happy path (context_specialist always returns text)
                # but keeps us honest for error paths.
                try:
                    r0.result = {"queue_updates": queue_updates}
                except Exception:
                    pass

        ack_bits = [
            "Thanks for your message.",
            f"I've noted it (ref {cinq[:12]}) and your RM will reach out.",
        ]
        if rreq:
            ack_bits.append(
                f"Also queued a research ask on {ticker} for the research team."
            )
        ack_bits.append("In the meantime, you can schedule a call.")
        ack = " ".join(ack_bits)
        return f"{ack}\n{_DISCLAIMER}"


def _mnpi_tripwire(text: str) -> str:
    """Last-line scrub: redact dollar amounts or share counts if any leak through."""
    text = re.sub(r"\$\s?\d[\d,]*(?:\.\d+)?", "[$REDACTED]", text)
    text = re.sub(r"\b\d{1,3}(?:,\d{3})+\s+shares?\b", "[SHARES_REDACTED]", text)
    return text


def _extract_ticker(query: str) -> str | None:
    """Grab the first 1-5 char uppercase token that looks like a ticker.

    Filter out common English words that happen to be uppercase (the
    false-positive rate is otherwise too high — "I", "A", "RM", "NYC").
    """
    _STOPWORDS = {
        "I", "A", "AN", "AS", "AT", "BE", "BY", "GO", "IF", "IN", "IS",
        "IT", "MY", "NO", "OF", "ON", "OR", "SO", "TO", "UP", "US", "WE",
        "RM", "NYC", "USD", "USA", "AM", "PM", "ET", "GMT", "UTC", "OK",
    }
    for m in re.finditer(r"\b([A-Z]{2,5})\b", query):
        token = m.group(1)
        if token not in _STOPWORDS:
            return token
    return None
