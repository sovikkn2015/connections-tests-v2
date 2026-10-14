"""
M9 Core Intent Classification — deterministic fast-path + LLM fallback.

classify_intent(user_input, aid_claims) → ClassificationResult

Flow:
  1. Deterministic regex/keyword matching for unambiguous intents (>95%)
  2. LLM function calling fallback (Haiku, <500ms target) for ambiguous input
  3. Confidence thresholds: >0.95 direct, 0.80-0.95 plan, <0.80 clarify

M9 calls M1 for identity verification and M5 for config via REST (Rule 13).
All tool calls through M6 gateway ONLY (Rule 7).
LLM provider abstracted via Protocol (Rule 9).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

import httpx

from models import (
    ClassificationResult,
    CompletionResponse,
    ConfidenceTier,
    FSIIntent,
    IntentCategory,
    LLMProvider,
    Message,
    ToolDefinition,
)
from taxonomy import (
    INTENT_TOOL_DEFINITIONS,
    KEYWORD_PATTERNS,
    TOOL_TO_CATEGORY,
    extract_params,
)

logger = logging.getLogger("m9.router")

# ── Confidence tier resolution (Rule 6) ──────────────────────────


def _resolve_tier(confidence: float) -> ConfidenceTier:
    """Map confidence score to routing tier."""
    if confidence > 0.95:
        return ConfidenceTier.direct
    if confidence >= 0.80:
        return ConfidenceTier.plan
    return ConfidenceTier.clarify


# ── Intent Router ────────────────────────────────────────────────


class IntentRouter:
    """
    FSI Intent Router — classifies natural language into structured intents.

    Args:
        llm_provider: Swappable LLM backend (Bedrock Haiku default).
        m1_base_url: M1 Identity service URL for AID verification.
        m5_base_url: M5 Config service URL for enterprise config.
    """

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        m1_base_url: str = "http://m1-identity:8000",
        m5_base_url: str = "http://m5-config:8000",
    ) -> None:
        self._llm = llm_provider
        self._m1_url = m1_base_url
        self._m5_url = m5_base_url
        self._http = httpx.AsyncClient(timeout=10.0)

    # ── Public API ───────────────────────────────────────────

    async def classify_intent(
        self,
        user_input: str,
        aid_claims: dict[str, Any] | None = None,
    ) -> ClassificationResult:
        """
        Classify user input into a structured FSI intent.

        Called by M12 (Agent Runtime) via REST.
        """
        start = time.perf_counter()
        text = user_input.strip()

        if not text:
            return self._empty_result(user_input, start)

        # Step 1: Deterministic fast-path (regex/keyword)
        result = self._deterministic_classify(text)
        if result is not None:
            elapsed = (time.perf_counter() - start) * 1000
            return ClassificationResult(
                intent=result,
                confidence_tier=_resolve_tier(result.confidence),
                raw_input=user_input,
                processing_time_ms=elapsed,
            )

        # Step 2: LLM fallback for ambiguous input
        if self._llm is not None:
            result = await self._llm_classify(text)
            if result is not None:
                elapsed = (time.perf_counter() - start) * 1000
                tier = _resolve_tier(result.confidence)
                candidates = (
                    [result] if tier == ConfidenceTier.clarify else []
                )
                return ClassificationResult(
                    intent=result,
                    confidence_tier=tier,
                    raw_input=user_input,
                    processing_time_ms=elapsed,
                    candidates=candidates,
                )

        # Step 3: No match — ask for clarification
        elapsed = (time.perf_counter() - start) * 1000
        return ClassificationResult(
            intent=FSIIntent(
                category=IntentCategory.client,
                action="unknown",
                confidence=0.0,
            ),
            confidence_tier=ConfidenceTier.clarify,
            raw_input=user_input,
            processing_time_ms=elapsed,
        )

    # ── Deterministic classification ─────────────────────────

    def _deterministic_classify(self, text: str) -> FSIIntent | None:
        """
        Regex/keyword matching for unambiguous intents.

        Returns FSIIntent with confidence >0.95 for clear patterns,
        or None if no pattern matches.
        """
        for pattern, category, action, confidence, extractor in KEYWORD_PATTERNS:
            match = pattern.search(text)
            if match:
                params = extract_params(text, match, extractor)
                return FSIIntent(
                    category=category,
                    action=action,
                    confidence=confidence,
                    parameters=params,
                )
        return None

    # ── LLM classification (Haiku, <500ms target) ────────────

    async def _llm_classify(self, text: str) -> FSIIntent | None:
        """
        LLM function calling fallback for ambiguous inputs.

        Uses the LLMProvider protocol — provider is swappable via config.
        Model: Haiku (Rule 8). Max tokens: 2,000 (Rule 4).
        """
        if self._llm is None:
            return None

        messages = [
            Message(
                role="system",
                content=(
                    "You are an FSI intent classifier. Classify the user's "
                    "message into exactly one financial services intent by "
                    "calling the appropriate classification tool. Set confidence "
                    "based on how clearly the message matches the intent."
                ),
            ),
            Message(role="user", content=text),
        ]

        try:
            response: CompletionResponse = await self._llm.complete(
                messages=messages,
                tools=INTENT_TOOL_DEFINITIONS,
                model="haiku",
                temperature=0.0,
                max_tokens=2000,
            )
        except Exception:
            logger.exception("LLM classification failed")
            return None

        return self._parse_llm_response(response)

    def _parse_llm_response(
        self, response: CompletionResponse,
    ) -> FSIIntent | None:
        """Parse LLM tool_use response into FSIIntent."""
        if not response.tool_calls:
            return None

        call = response.tool_calls[0]
        tool_name = call.get("name", "")
        category = TOOL_TO_CATEGORY.get(tool_name)
        if category is None:
            return None

        args = call.get("input", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, TypeError):
                return None

        action = args.get("action", "unknown")
        confidence = float(args.get("confidence", 0.5))

        # Build parameters from remaining args
        params: dict[str, Any] = {
            k: v for k, v in args.items()
            if k not in ("action", "confidence") and v is not None
        }

        return FSIIntent(
            category=category,
            action=action,
            confidence=confidence,
            parameters=params,
        )

    # ── Helpers ───────────────────────────────────────────────

    def _empty_result(
        self, raw_input: str, start: float,
    ) -> ClassificationResult:
        elapsed = (time.perf_counter() - start) * 1000
        return ClassificationResult(
            intent=FSIIntent(
                category=IntentCategory.client,
                action="unknown",
                confidence=0.0,
            ),
            confidence_tier=ConfidenceTier.clarify,
            raw_input=raw_input,
            processing_time_ms=elapsed,
        )

    async def verify_identity(self, token: str) -> dict[str, Any] | None:
        """Verify AID token via M1 (Rule 13 — REST, no cross-module import)."""
        try:
            resp = await self._http.post(
                f"{self._m1_url}/aid/verify",
                json={"token": token},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("valid"):
                    return data.get("claims")
        except httpx.HTTPError:
            logger.warning("M1 identity verification unavailable")
        return None

    async def close(self) -> None:
        """Clean up HTTP client."""
        await self._http.aclose()
