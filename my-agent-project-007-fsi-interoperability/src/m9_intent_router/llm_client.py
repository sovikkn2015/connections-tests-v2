"""
M9 Intent Router -- LLM provider abstraction (R4, AC4.1-4.9).

- LLMProvider Protocol: runtime-checkable, one method classify().
- BedrockHaikuClient: Bedrock Runtime converse() with Anthropic tool_use.
- FakeLlmClient: deterministic fake for tests (Fix 9 -- Exception injection).
- SlowFakeLlmClient: deterministic timeout fake (Fix 13).
- AzureOpenAIClient / VertexClient / VllmClient: reserved Phase 3 stubs.
- select_provider(config): dispatch on config.provider.

boto3 imported ONLY here and in hmac_util.py (AC13.3).

See `.kiro/specs/m9-intent-router.md` R3, R4, Appendix B.1.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from m9_intent_router.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m9_intent_router.models import LlmClassification
from m9_intent_router.taxonomy import IntentCategory


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol every M9 LLM provider must satisfy (R4).

    Single method: classify(utterance, taxonomy_schema) -> LlmClassification.
    Raises LlmTimeoutError / LlmProviderError / LlmMalformedOutputError on
    failure (AC3.4). Never raises any other exception class.
    """

    def classify(
        self, utterance: str, taxonomy_schema: dict
    ) -> LlmClassification: ...


# -----------------------------------------------------------------------------
# BedrockHaikuClient (Phase 2 production provider).
# -----------------------------------------------------------------------------


class BedrockHaikuClient:
    """Bedrock Claude Haiku provider via boto3 bedrock-runtime.converse (AC3.1).

    Constructor stores config; the boto3 client is created at init but makes
    no network call until .classify() invoked. Credentials resolve via the
    default chain (IRSA -> instance meta -> env -> Vault) per R14 AC14.2.

    Retries capped at max_retries=2 for 5xx AND timeout ONLY (never 4xx per
    AC3.5). Exponential backoff 100ms * 2^n with +-25% jitter.
    """

    def __init__(
        self,
        model_id: str,
        region: str,
        timeout_ms: int,
        max_retries: int = 2,
    ) -> None:
        import boto3  # AC13.3 -- boto3 allowed in llm_client.py
        from botocore.config import Config

        self._model_id = model_id
        self._region = region
        self._timeout_ms = timeout_ms
        self._max_retries = max_retries
        read_timeout_s = max(1, timeout_ms / 1000.0)
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                read_timeout=read_timeout_s,
                connect_timeout=read_timeout_s,
                retries={"max_attempts": 1},  # we do our own retry loop
            ),
        )

    def classify(
        self, utterance: str, taxonomy_schema: dict
    ) -> LlmClassification:
        """Issue a Bedrock converse() call and parse the tool_use response.

        Returns LlmClassification or raises one of three error classes (AC3.4).
        """
        import random

        from botocore.exceptions import ClientError, ReadTimeoutError

        system_prompt = _load_system_prompt()
        start = time.perf_counter()
        attempt = 0
        while True:
            try:
                resp = self._client.converse(
                    modelId=self._model_id,
                    messages=[
                        {
                            "role": "user",
                            "content": [{"text": utterance}],
                        }
                    ],
                    system=[{"text": system_prompt}],
                    toolConfig=taxonomy_schema,
                    inferenceConfig={
                        "temperature": 0.0,
                        "maxTokens": 2000,
                        "topP": 1.0,
                    },
                )
                latency_ms = int((time.perf_counter() - start) * 1000)
                return _parse_bedrock_response(resp, latency_ms, self._model_id)
            except ReadTimeoutError as exc:
                attempt += 1
                if attempt > self._max_retries:
                    raise LlmTimeoutError(
                        f"Bedrock read timeout after {self._max_retries} retries"
                    ) from exc
                _sleep_backoff(attempt, random.random)
                continue
            except ClientError as exc:
                status = exc.response.get("ResponseMetadata", {}).get(
                    "HTTPStatusCode", 500
                )
                if 400 <= status < 500:
                    raise LlmProviderError(status, str(exc)) from exc
                # 5xx -- retry
                attempt += 1
                if attempt > self._max_retries:
                    raise LlmProviderError(status, str(exc)) from exc
                _sleep_backoff(attempt, random.random)
                continue


def _sleep_backoff(attempt: int, rand_fn) -> None:
    """Exponential backoff 100ms * 2^n with +-25% jitter."""
    base_ms = 100 * (2 ** (attempt - 1))
    jitter = base_ms * 0.25 * (2 * rand_fn() - 1)
    time.sleep(max(0.0, (base_ms + jitter) / 1000.0))


def _load_system_prompt() -> str:
    """Load the system prompt from the shipped markdown file."""
    import pathlib

    here = pathlib.Path(__file__).parent
    return (here / "prompts" / "system.md").read_text(encoding="utf-8")


def _parse_bedrock_response(
    resp: dict, latency_ms: int, model_id: str
) -> LlmClassification:
    """Parse a Bedrock converse() response into an LlmClassification.

    Parsing rules (LLM Contract JSON Schema Example):
    1. stopReason must be "tool_use".
    2. content must have exactly one toolUse block.
    3. toolUse.name must equal "routing_decision".
    4. input must validate against LlmClassification (Pydantic).
    """
    from pydantic import ValidationError

    try:
        if resp.get("stopReason") != "tool_use":
            raise LlmMalformedOutputError(
                f"unexpected stopReason: {resp.get('stopReason')!r}"
            )
        content = resp.get("output", {}).get("message", {}).get("content", [])
        tool_uses = [c["toolUse"] for c in content if "toolUse" in c]
        if len(tool_uses) != 1:
            raise LlmMalformedOutputError(
                f"expected exactly one toolUse, got {len(tool_uses)}"
            )
        tu = tool_uses[0]
        if tu.get("name") != "routing_decision":
            raise LlmMalformedOutputError(
                f"model hallucinated tool name: {tu.get('name')!r}"
            )
        payload = tu.get("input", {})
        ents = payload.get("entities", {}) or {}
        known_slots = {
            "ticker",
            "client_id",
            "household_id",
            "account_id",
            "date_range",
        }
        filtered = {k: v for k, v in ents.items() if k in known_slots}
        return LlmClassification(
            intent=IntentCategory(payload.get("intent")),
            confidence=payload.get("confidence"),
            entities=filtered,
            latency_ms=latency_ms,
            model=model_id,
            provider="bedrock",
        )
    except ValidationError as exc:
        raise LlmMalformedOutputError(
            f"pydantic rejected tool output: {exc}"
        ) from exc
    except (KeyError, TypeError, ValueError) as exc:
        raise LlmMalformedOutputError(str(exc)) from exc


# -----------------------------------------------------------------------------
# Fake providers (tests only).
# -----------------------------------------------------------------------------


class FakeLlmClient:
    """Deterministic fake provider for tests and benchmarks (AC4.3 + Fix 9).

    ``responses`` dict may be keyed by either the utterance itself (simple
    test path) or by the HMAC-SHA-256 utterance digest. The fake tries
    utterance-direct first, then falls through to UNSUPPORTED.

    Values may be LlmClassification (returned) or Exception (raised verbatim).
    """

    def __init__(
        self,
        responses: "dict[str, LlmClassification | Exception] | None" = None,
        classify_latency_ms: int = 0,
    ) -> None:
        self._responses = dict(responses or {})
        self._classify_latency_ms = classify_latency_ms

    def classify(
        self, utterance: str, taxonomy_schema: dict
    ) -> LlmClassification:
        if self._classify_latency_ms:
            time.sleep(self._classify_latency_ms / 1000.0)
        result = self._responses.get(utterance)
        if isinstance(result, Exception):
            raise result  # Fix 9
        if isinstance(result, LlmClassification):
            return result
        return LlmClassification(
            intent=IntentCategory.UNSUPPORTED,
            confidence=0.0,
            entities={},
            latency_ms=self._classify_latency_ms,
            model="fake",
            provider="fake",
        )


class SlowFakeLlmClient:
    """Slow fake provider for deterministic timeout tests (AC4.9, Fix 13).

    Sleeps min(block_ms, timeout_ms) ms, then raises LlmTimeoutError if
    block_ms > timeout_ms. Satisfies LLMProvider.
    """

    def __init__(self, block_ms: int, timeout_ms: int) -> None:
        self._block_ms = block_ms
        self._timeout_ms = timeout_ms

    def classify(
        self, utterance: str, taxonomy_schema: dict
    ) -> LlmClassification:
        sleep_ms = min(self._block_ms, self._timeout_ms)
        time.sleep(sleep_ms / 1000.0)
        if self._block_ms > self._timeout_ms:
            raise LlmTimeoutError(
                f"blocked {self._block_ms}ms > timeout {self._timeout_ms}ms"
            )
        return LlmClassification(
            intent=IntentCategory.UNSUPPORTED,
            confidence=0.0,
            entities={},
            latency_ms=sleep_ms,
            model="slow_fake",
            provider="fake",
        )


# -----------------------------------------------------------------------------
# Reserved Phase 3 stubs (AC4.4).
# -----------------------------------------------------------------------------


class AzureOpenAIClient:
    """Reserved for Phase 3."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("Phase 3 -- AzureOpenAIClient reserved")

    def classify(
        self, utterance: str, taxonomy_schema: dict
    ) -> LlmClassification:
        raise NotImplementedError("Phase 3")


class VertexClient:
    """Reserved for Phase 3."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("Phase 3 -- VertexClient reserved")

    def classify(
        self, utterance: str, taxonomy_schema: dict
    ) -> LlmClassification:
        raise NotImplementedError("Phase 3")


class VllmClient:
    """Reserved for Phase 3."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("Phase 3 -- VllmClient reserved")

    def classify(
        self, utterance: str, taxonomy_schema: dict
    ) -> LlmClassification:
        raise NotImplementedError("Phase 3")


# -----------------------------------------------------------------------------
# select_provider dispatch (AC4.5).
# -----------------------------------------------------------------------------


def select_provider(config) -> LLMProvider:
    """Construct the LLM provider from a duck-typed IntentRouterConfig.

    Requires ``config.provider``, ``config.model_id``, ``config.region``,
    ``config.timeout_ms``. Unknown provider -> ValueError("provider_unconfigured").

    TODO(M5 v0.3.0): switch to m5_config_loader.IntentRouterConfig per AC12.4.
    """
    provider = getattr(config, "provider", None)
    if provider == "bedrock":
        return BedrockHaikuClient(
            model_id=config.model_id,
            region=config.region,
            timeout_ms=config.timeout_ms,
        )
    if provider == "azure_openai":
        return AzureOpenAIClient()
    if provider == "vertex":
        return VertexClient()
    if provider == "vllm":
        return VllmClient()
    raise ValueError("provider_unconfigured")
