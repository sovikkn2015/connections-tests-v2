"""Stubs for pure-module tests. Not used in production.

StubBedrockClient returns canned responses matching the shape that real
Bedrock Converse API emits, so orchestrators and specialists can be unit
tested without AWS credentials.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class StubBedrockClient:
    """Drop-in replacement for a real Bedrock Converse client.

    Ships with sensible defaults for each specialist's expected output shape.
    Tests can override by supplying `canned_responses` keyed by a substring
    of the user prompt (first match wins) or by agent_id.
    """

    def __init__(
        self,
        canned_responses: Optional[Dict[str, Dict[str, Any]]] = None,
        default_latency_ms: int = 10,
    ) -> None:
        self._canned = canned_responses or {}
        self._latency = default_latency_ms
        self.call_history: List[Dict[str, Any]] = []

    async def converse(
        self,
        *,
        model_id: str,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        agent_id: Optional[str] = None,
        tool_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return a canned Bedrock Converse-style response.

        When `tool_config` is provided and the stub has a scripted tool_use
        response for this agent_id, return a tool_use response on the first
        call and an end_turn response on subsequent calls. This lets tests
        exercise the tool-use dispatch loop without a live model.
        """
        self.call_history.append(
            {
                "model_id": model_id,
                "agent_id": agent_id,
                "messages": messages,
                "system_chars": len(system_prompt),
                "tool_config_tools": [
                    t["toolSpec"]["name"] for t in (tool_config or {}).get("tools", [])
                ] if tool_config else [],
            }
        )

        user_text = ""
        if messages:
            last = messages[-1]
            content = last.get("content", [])
            if content and isinstance(content, list):
                user_text = content[0].get("text", "") if isinstance(content[0], dict) else ""

        response = None
        if agent_id and agent_id in self._canned:
            response = self._canned[agent_id]
        else:
            for key, val in self._canned.items():
                if key.lower() in user_text.lower():
                    response = val
                    break

        if response is None:
            response = self._default_response(agent_id or "unknown")

        return {
            "output": {"message": {"content": [{"text": response.get("text", "")}]}},
            "usage": {
                "inputTokens": response.get("input_tokens", 100),
                "outputTokens": response.get("output_tokens", 50),
            },
            "stopReason": "end_turn",
            "_stub_meta": {"agent_id": agent_id, "latency_ms": self._latency},
        }

    @staticmethod
    def _default_response(agent_id: str) -> Dict[str, Any]:
        """Canned defaults aligned with each specialist's output contract."""
        defaults: Dict[str, Dict[str, Any]] = {
            "research_orchestrator": {
                "text": (
                    "Brief synthesized from 5 specialist responses. "
                    "Thesis: stable fundamentals. Sentiment: neutral. [src:stub_orch_001]"
                ),
                "input_tokens": 800,
                "output_tokens": 350,
            },
            "market_specialist": {
                "text": '{"ticker": "NVDA", "price": 162.15, "change_pct": -0.021, '
                        '"source_chunk_id": "stub_mkt_001"}',
                "input_tokens": 80,
                "output_tokens": 40,
            },
            "filings_specialist": {
                "text": '{"filing_type": "10-Q", "citations": ["stub_fil_001"]}',
                "input_tokens": 400,
                "output_tokens": 180,
            },
            "sentiment_specialist": {
                "text": '{"sentiment_score": 0.15, "confidence": 0.7, '
                        '"source_chunk_ids": ["stub_sent_001"]}',
                "input_tokens": 250,
                "output_tokens": 80,
            },
            "compliance_specialist": {
                "text": '{"status": "ALLOW", "restricted_list_hit": false, "mnpi_flag": false}',
                "input_tokens": 120,
                "output_tokens": 30,
            },
            "statement_specialist": {
                "text": '{"analyses_run": ["gross_margin_trend"], '
                        '"source_chunk_ids": ["stub_stmt_001"]}',
                "input_tokens": 300,
                "output_tokens": 120,
            },
            "advisor_orchestrator": {
                "text": (
                    "Based on brief by Sarah Chen: 3 clients over 5% NVDA concentration, "
                    "no contact 7d+. [src:stub_adv_001]"
                ),
                "input_tokens": 600,
                "output_tokens": 240,
            },
            "portfolio_specialist": {
                "text": '{"concentration_flags": [], "citations": ["stub_port_001"]}',
                "input_tokens": 300,
                "output_tokens": 100,
            },
            "suitability_specialist": {
                "text": '{"status": "PASS", "reasons": []}',
                "input_tokens": 100,
                "output_tokens": 30,
            },
            "client_context_specialist": {
                "text": '{"household": "Patel", "positions_pct": [{"ticker":"NVDA","pct":6.2}]}',
                "input_tokens": 250,
                "output_tokens": 120,
            },
            "action_specialist": {
                "text": '{"final_status": "COMPLIANCE_DENIED", "action_plan": null}',
                "input_tokens": 500,
                "output_tokens": 80,
            },
            "liaison_orchestrator": {
                "text": "Escalated to your RM.",
                "input_tokens": 150,
                "output_tokens": 30,
            },
            "faq_specialist": {
                "text": (
                    "Markets open 9:30-4:00 ET on weekdays. "
                    "For informational purposes. Your RM makes recommendations."
                ),
                "input_tokens": 60,
                "output_tokens": 40,
            },
            "context_specialist": {
                "text": '{"client_household_summary": "High-level only; details with your RM."}',
                "input_tokens": 200,
                "output_tokens": 60,
            },
        }
        return defaults.get(
            agent_id,
            {"text": f"[stub response for {agent_id}]", "input_tokens": 10, "output_tokens": 5},
        )


class StubLangfuseSpan:
    """Drop-in Langfuse span that records calls without a network hop."""

    def __init__(self, name: str, parent: Optional["StubLangfuseSpan"] = None) -> None:
        self.name = name
        self.parent = parent
        self.children: List["StubLangfuseSpan"] = []
        self.metadata: Dict[str, Any] = {}
        self.ended = False

    def span(self, name: str) -> "StubLangfuseSpan":
        child = StubLangfuseSpan(name=name, parent=self)
        self.children.append(child)
        return child

    def update(self, **kwargs: Any) -> None:
        self.metadata.update(kwargs)

    def end(self) -> None:
        self.ended = True

    def __enter__(self) -> "StubLangfuseSpan":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.end()


class StubLangfuseClient:
    """Drop-in Langfuse client. Captures span tree for test assertions."""

    def __init__(self) -> None:
        self.spans: List[StubLangfuseSpan] = []

    def trace(self, name: str, **_kwargs: Any) -> StubLangfuseSpan:
        span = StubLangfuseSpan(name=name)
        self.spans.append(span)
        return span
