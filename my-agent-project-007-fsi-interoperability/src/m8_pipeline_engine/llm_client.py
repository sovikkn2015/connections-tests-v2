"""
M8 Pipeline Engine -- LLMClient Protocol + Bedrock Sonnet implementation.

Steering Rule 13 (Sonnet for research) + Steering Rule 15 (provider abstract).
Zero credentials (boto3 default chain). boto3 confined to this file + hitl.py
+ checkpointer.py per AC13.3.

See `.kiro/specs/m8-pipeline-engine.md` R6.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any, Literal, Optional, Protocol, runtime_checkable

from m8_pipeline_engine.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m8_pipeline_engine.models import LlmGeneration

try:  # boto3 optional at test time
    import boto3
    import botocore.exceptions as _boto_exc
except Exception:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]
    _boto_exc = None  # type: ignore[assignment]


@runtime_checkable
class LLMClient(Protocol):
    def generate(
        self,
        *,
        stage_name: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: Literal["text", "json"],
    ) -> LlmGeneration:
        ...


def _input_sha256(stage_name: str, prompt: str) -> str:
    return hashlib.sha256(
        (stage_name + "\x00" + prompt).encode("utf-8")
    ).hexdigest()


class SonnetClient:
    """Bedrock Runtime Converse API wrapper (AC6.3-6.8)."""

    provider: Literal["bedrock"] = "bedrock"

    def __init__(
        self,
        model_id: str,
        region: str,
        timeout_ms: int = 60000,
        max_retries: int = 2,
    ) -> None:
        self._model_id = model_id
        self._region = region
        self._timeout_ms = timeout_ms
        self._max_retries = max_retries
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            if boto3 is None:
                raise RuntimeError("boto3_not_installed")
            self._client = boto3.client(
                "bedrock-runtime", region_name=self._region
            )
        return self._client

    def generate(
        self,
        *,
        stage_name: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: Literal["text", "json"] = "text",
    ) -> LlmGeneration:
        client = self._get_client()
        body = {
            "modelId": self._model_id,
            "messages": [
                {"role": "user", "content": [{"text": prompt}]}
            ],
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
        }
        if response_format == "json":
            body["additionalModelRequestFields"] = {
                "response_format": {"type": "json_object"}
            }

        backoff_ms = 500
        last_exc: Optional[BaseException] = None
        for attempt in range(self._max_retries + 1):
            start = time.perf_counter()
            try:
                response = client.converse(**body)
                latency_ms = int((time.perf_counter() - start) * 1000)
                return _parse_converse_response(
                    response,
                    model_id=self._model_id,
                    latency_ms=latency_ms,
                    response_format=response_format,
                )
            except Exception as exc:
                last_exc = exc
                mapped = _map_bedrock_exception(exc)
                if isinstance(mapped, LlmProviderError) and 400 <= mapped.status_code < 500:
                    raise mapped
                if attempt >= self._max_retries:
                    raise mapped
                time.sleep(backoff_ms / 1000.0)
                backoff_ms *= 2
        if last_exc:
            raise LlmProviderError(500, str(last_exc))
        raise LlmProviderError(500)


def _parse_converse_response(
    response: Any,
    *,
    model_id: str,
    latency_ms: int,
    response_format: str,
) -> LlmGeneration:
    try:
        output_msg = response["output"]["message"]
        content = output_msg["content"]
        text_parts = [c.get("text", "") for c in content if isinstance(c, dict)]
        text = "".join(text_parts)
        usage = response.get("usage", {})
        stop_reason = response.get("stopReason", "end_turn")
    except (KeyError, TypeError) as exc:
        raise LlmMalformedOutputError(f"converse_parse: {exc!r}")

    if response_format == "json":
        import json as _json
        try:
            _json.loads(text)
        except Exception as exc:
            raise LlmMalformedOutputError(f"json_parse: {exc!r}")

    return LlmGeneration(
        text=text,
        input_tokens=int(usage.get("inputTokens", 0)),
        output_tokens=int(usage.get("outputTokens", 0)),
        latency_ms=latency_ms,
        model=model_id,
        provider="bedrock",
        stop_reason=stop_reason,
    )


def _map_bedrock_exception(exc: BaseException) -> BaseException:
    if _boto_exc is not None and isinstance(
        exc, (_boto_exc.ReadTimeoutError, _boto_exc.ConnectTimeoutError)
    ):
        return LlmTimeoutError(str(exc))
    if _boto_exc is not None and isinstance(exc, _boto_exc.ClientError):
        meta = exc.response.get("ResponseMetadata", {})
        status = int(meta.get("HTTPStatusCode", 500))
        return LlmProviderError(status, str(exc))
    if isinstance(exc, (LlmProviderError, LlmTimeoutError, LlmMalformedOutputError)):
        return exc
    return LlmProviderError(500, str(exc))


class FakeSonnetClient:
    """Test LLMClient. Seeded by input_sha256(stage_name+prompt) or stage_name."""

    provider: Literal["fake"] = "fake"

    def __init__(
        self,
        responses: Optional[dict[str, Any]] = None,
        delay_ms: int = 0,
        default_model: str = "fake-sonnet",
    ) -> None:
        self.responses: dict[str, Any] = dict(responses or {})
        self._delay = delay_ms / 1000.0
        self._default_model = default_model
        self.recorded: list[tuple[str, str, int, float]] = []

    def generate(
        self,
        *,
        stage_name: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: Literal["text", "json"] = "text",
    ) -> LlmGeneration:
        if self._delay > 0:
            time.sleep(self._delay)
        digest = _input_sha256(stage_name, prompt)
        self.recorded.append((stage_name, digest, max_tokens, temperature))
        if digest in self.responses:
            value = self.responses[digest]
        elif stage_name in self.responses:
            value = self.responses[stage_name]
        else:
            value = None
        if isinstance(value, Exception):
            raise value
        if isinstance(value, LlmGeneration):
            return value
        return LlmGeneration(
            text="{}" if response_format == "json" else "fake response",
            input_tokens=len(prompt.split()),
            output_tokens=2,
            latency_ms=1,
            model=self._default_model,
            provider="fake",
            stop_reason="end_turn",
        )


class AzureOpenAIClient:
    provider: Literal["azure_openai"] = "azure_openai"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Phase 3")

    def generate(self, **kwargs: Any) -> LlmGeneration:  # pragma: no cover
        raise NotImplementedError("Phase 3")


class VertexClient:
    provider: Literal["vertex"] = "vertex"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Phase 3")

    def generate(self, **kwargs: Any) -> LlmGeneration:  # pragma: no cover
        raise NotImplementedError("Phase 3")


class VllmClient:
    provider: Literal["vllm"] = "vllm"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Phase 3")

    def generate(self, **kwargs: Any) -> LlmGeneration:  # pragma: no cover
        raise NotImplementedError("Phase 3")


def select_llm_client(config: Any) -> LLMClient:
    """Sole construction point (AC6.12)."""
    provider = getattr(config, "model_provider", None)
    model_id = getattr(
        config, "model_id", "anthropic.claude-sonnet-4-5-20250929-v1:0"
    )
    region = getattr(config, "region", "us-east-1")
    timeout_ms = getattr(config, "timeout_ms", 60000)

    if provider == "bedrock":
        return SonnetClient(
            model_id=model_id, region=region, timeout_ms=timeout_ms
        )
    if provider == "azure_openai":
        return AzureOpenAIClient(model_id=model_id)
    if provider == "vertex":
        return VertexClient(model_id=model_id)
    if provider == "vllm":
        return VllmClient(model_id=model_id)
    raise ValueError("provider_unconfigured")


__all__ = [
    "LLMClient",
    "SonnetClient",
    "FakeSonnetClient",
    "AzureOpenAIClient",
    "VertexClient",
    "VllmClient",
    "select_llm_client",
]
