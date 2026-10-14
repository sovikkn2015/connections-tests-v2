"""Advisor orchestrator — the RM's agent.

Classifies intent and routes: parallel fanout for read-path
(research-aware-advisory, portfolio-analytics, suitability-check) and strictly
serial execution for action-write (compliance -> HITL -> dual-auth ->
mulesoft-api -> audit — the seven-gate trust spine).
"""

from __future__ import annotations

import re
from enum import Enum
from typing import List

from .coordinator import Orchestrator
from .messages import OrchestratorDispatch, SessionContext, WorkerResponse


class AdvisorIntent(str, Enum):
    """Five advisor intent classes."""

    RESEARCH_AWARE = "research_aware"
    PORTFOLIO = "portfolio"
    SUITABILITY = "suitability"
    ACTION_WRITE = "action_write"
    CLIENT_REPLY = "client_reply"


_ACTION_VERBS = re.compile(
    r"\b(buy|sell|trim|liquidate|rebalance|wire|transfer|close\s+account|"
    r"submit\s+order|modify\s+order|cancel\s+order)\b",
    re.IGNORECASE,
)
_CLIENT_REPLY_KEYWORDS = (
    "tell the client",
    "tell mrs",
    "tell mr",
    "reply to",
    "message the client",
    "send to client",
    "notify the client",
    "let the client know",
    "inform the client",
    "reach out to",
)
_SUITABILITY_KEYWORDS = ("suitable", "suitability", "risk profile", "appropriate for")
_PORTFOLIO_KEYWORDS = (
    "portfolio",
    "allocation",
    "attribution",
    "drawdown",
    "concentration",
    "exposure",
)


def classify_intent(query: str) -> AdvisorIntent:
    """Classify the RM's query into one of four intent classes.

    Ordering:
    - ACTION_WRITE wins over everything (write-path is never masked).
    - SUITABILITY next (explicit regulatory frame).
    - PORTFOLIO next (pure analytics without research join).
    - RESEARCH_AWARE is the default.
    """
    if _ACTION_VERBS.search(query):
        return AdvisorIntent.ACTION_WRITE
    low = query.lower()
    if any(k in low for k in _CLIENT_REPLY_KEYWORDS):
        return AdvisorIntent.CLIENT_REPLY
    if any(k in low for k in _SUITABILITY_KEYWORDS):
        return AdvisorIntent.SUITABILITY
    if any(k in low for k in _PORTFOLIO_KEYWORDS) and "brief" not in low:
        return AdvisorIntent.PORTFOLIO
    return AdvisorIntent.RESEARCH_AWARE


class AdvisorOrchestratorImpl(Orchestrator):
    """Concrete advisor-orchestrator. Reads parallelize; writes serialize."""

    async def plan(
        self,
        query: str,
        ctx: SessionContext,
    ) -> List[OrchestratorDispatch]:
        """Dispatch set depends on classified intent."""
        intent = classify_intent(query)
        ticker = _extract_ticker(query)

        if intent is AdvisorIntent.ACTION_WRITE:
            # Write-path: action_specialist ONLY. Specialist sequences the
            # seven gates internally. Never parallelize here.
            #
            # DRAFT-ONLY MODE (2026-04-30): the frontend calls /agent/invoke
            # through an API Gateway REST endpoint which has a 29s hard
            # timeout. A real seven-gate sequence (including blocking HITL)
            # cannot complete synchronously. We split the turn in two:
            #
            #   Turn 1 (this dispatch): action_specialist runs gates 1-3
            #     (guardrails, MNPI filter, compliance_screening), drafts
            #     the ActionPlan, and returns. ~5-10s. Fits in 29s.
            #
            #   Turn 2 (on approval): POST /agent/approve runs gates 4-7
            #     (HITL verify, dual_auth, mulesoft, audit) synchronously
            #     from the AgentProxy Lambda. ~2-5s. Returns a canonical
            #     gate_trace the frontend replays.
            #
            # The [DRAFT_ONLY] directive tells the LLM: do not call hitl,
            # dual_auth, mulesoft_api, or audit_logging in this turn. Stop
            # after compliance_screening and return the structured plan.
            return [
                OrchestratorDispatch(
                    target_agent_id="action_specialist",
                    task=(
                        f"[DRAFT_ONLY mode — API Gateway 29s timeout]\n"
                        f"Run gates 1-3 only: guardrails verification, MNPI "
                        f"filter on the incoming intent, and compliance_screening "
                        f"skill. Then STOP and return a JSON body with "
                        f"{{action_plan, gate_trace[], final_status: 'PENDING_APPROVAL'}}.\n"
                        f"Do NOT call the hitl, dual_auth, mulesoft_api, or "
                        f"audit_logging skills in this turn — those run in the "
                        f"approval round-trip after the RM reviews the plan.\n"
                        f"The action_plan JSON must include: plan_id "
                        f"(generate a unique id), action_type "
                        f"(submit_order|cancel_order|modify_order|initiate_wire), "
                        f"summary (one-line human-readable), client_household, "
                        f"notional_usd (estimated $ amount), requires_dual_auth "
                        f"(true if wire > $100K or trade > $500K).\n\n"
                        f"RM instruction: {query}"
                    ),
                    context_subset={"ticker": ticker, "principal_id": ctx.principal_id},
                    timeout_s=26.0,
                )
            ]

        if intent is AdvisorIntent.CLIENT_REPLY:
            # RM wants to reply to a client. Use client_context_specialist
            # to draft a compliant, MNPI-safe reply. The synthesize step
            # will emit a queue_update to the client persona's inbox so
            # the reply appears in Eleanor's WhatsApp thread.
            return [
                OrchestratorDispatch(
                    target_agent_id="client_context_specialist",
                    task=(
                        f"The RM wants to send a message to the client. "
                        f"Draft a compliant, MNPI-safe reply based on the RM's "
                        f"instruction. The reply must NOT contain share counts, "
                        f"dollar amounts, or specific recommendations — only "
                        f"general context and next steps. Include a disclaimer.\n\n"
                        f"RM instruction: {query}"
                    ),
                    context_subset={"ticker": ticker, "principal_id": ctx.principal_id},
                    timeout_s=20.0,
                )
            ]

        if intent is AdvisorIntent.SUITABILITY:
            return [
                OrchestratorDispatch(
                    target_agent_id="suitability_specialist",
                    task=(
                        f"Run a suitability check for the RM's query. "
                        f"Return PASS/FAIL/REVIEW with reasons.\n\nQuery: {query}"
                    ),
                    context_subset={"ticker": ticker},
                    timeout_s=20.0,
                )
            ]

        if intent is AdvisorIntent.PORTFOLIO:
            return [
                OrchestratorDispatch(
                    target_agent_id="portfolio_specialist",
                    task=(
                        f"Run portfolio analytics for the query. Work in percentages, "
                        f"not absolute dollars. Return concentration flags + citations."
                        f"\n\nQuery: {query}"
                    ),
                    context_subset={"ticker": ticker},
                    timeout_s=25.0,
                )
            ]

        # RESEARCH_AWARE default: parallel fanout to portfolio + client_context.
        return [
            OrchestratorDispatch(
                target_agent_id="client_context_specialist",
                task=(
                    f"Fetch MNPI-filtered client context relevant to this query."
                    f"\n\nQuery: {query}"
                ),
                context_subset={"ticker": ticker},
                timeout_s=25.0,
            ),
            OrchestratorDispatch(
                target_agent_id="portfolio_specialist",
                task=(
                    f"Portfolio-level relevance for the query. Positions in "
                    f"percentages. Return concentration flags.\n\nQuery: {query}"
                ),
                context_subset={"ticker": ticker},
                timeout_s=25.0,
            ),
        ]

    async def synthesize(
        self,
        query: str,
        ctx: SessionContext,
        responses: List[WorkerResponse],
    ) -> str:
        """Combine specialist outputs into an RM-facing answer.

        For CLIENT_REPLY intent, also stash a queue_update on the first
        response so the client channel receives the RM's reply in real time.
        """
        intent = classify_intent(query)
        sections: List[str] = []
        citations: List[str] = []
        had_error = False

        for r in responses:
            citations.extend(r.citations)
            if r.errors:
                had_error = True
                sections.append(
                    f"## {r.agent_id}\nerror: {r.errors[0].message}"
                )
                continue
            text = r.result.get("text", "") or ""
            sections.append(f"## {r.agent_id}\n{text}")

        # For CLIENT_REPLY: emit a queue_update to the client's inbox
        # so the reply appears in Eleanor's WhatsApp thread in real time.
        if intent is AdvisorIntent.CLIENT_REPLY and responses:
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            reply_text = ""
            for r in responses:
                if not r.errors and r.result:
                    reply_text = r.result.get("text", "") or ""
                    break
            if reply_text:
                queue_updates = [{
                    "queue": "inbox",
                    "op": "add",
                    "item_id": f"rm-reply-{ctx.correlation_id}",
                    "item": {
                        "id": f"rm-reply-{ctx.correlation_id}",
                        "kind": "inbox",
                        "title": f"RM reply",
                        "subtitle": reply_text[:200],
                        "badge": "from RM",
                        "timestamp": now_iso,
                        "unread": True,
                    },
                }]
                r0 = responses[0]
                if hasattr(r0, "result") and isinstance(r0.result, dict):
                    r0.result["queue_updates"] = queue_updates

        header = (
            f"# RM Response (intent={intent.value}, session {ctx.session_id})\n"
        )
        if ctx.parent_brief_id:
            header += f"Based on brief: {ctx.parent_brief_id}\n"
        if had_error:
            header += "note: one or more specialists returned errors\n"

        body = "\n\n".join(sections)
        footer = (
            "\n\nCitations: " + ", ".join(sorted(set(citations))) if citations else ""
        )
        return f"{header}\n{body}{footer}"


def _extract_ticker(query: str) -> str:
    """Naive ticker extractor: first uppercase 1-5 char token."""
    m = re.search(r"\b([A-Z]{1,5})\b", query)
    return m.group(1) if m else ""
