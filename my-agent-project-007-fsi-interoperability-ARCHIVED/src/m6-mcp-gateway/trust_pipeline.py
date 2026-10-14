"""
M6 Trust Pipeline — Pre-call and Post-call orchestration.

Pre-call (Rule 2):
  1. M1 — Verify AID (JWT RS256 + FSI claims)
  2. M2 — Check authority (OPA policy evaluation)
  3. M4 — Filter MNPI from request fields

Post-call (Rule 3):
  1. M7 — Translate vendor response to canonical format
  2. M4 — Filter MNPI from response fields
  3. MNPI Leakage Scan — 3-layer guardrail (Rule 10)
  4. M10 — Write audit log entry (all 3 tiers)

Each stage adds SHA-256 hash to provenance chain (Rule 11).
If ANY step fails → DENIED. No degraded mode (Rule 12).

All module calls via REST (Rule 14). No cross-module imports.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any, Optional

import httpx
from opentelemetry import trace

from .leakage_scan import scan_output
from .models import (
    GatewayConfig,
    PipelineStage,
    ProvenanceEntry,
    TrustPipelineResult,
)

_tracer = trace.get_tracer("m6.mcp-gateway")

logger = logging.getLogger("m6.trust_pipeline")


def _hash_payload(payload: Any) -> str:
    """Compute SHA-256 hash of a JSON-serializable payload."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _add_provenance(
    chain: list[ProvenanceEntry],
    stage: PipelineStage,
    module: str,
    payload: Any,
) -> list[ProvenanceEntry]:
    """Append a provenance entry with SHA-256 hash of the current payload."""
    entry = ProvenanceEntry(
        stage=stage,
        module=module,
        hash=_hash_payload(payload),
    )
    chain.append(entry)
    return chain


class TrustPipeline:
    """
    Orchestrates pre-call and post-call trust pipelines.

    All module dependencies (M1, M2, M4, M7, M10) are called via
    REST using httpx. No cross-module imports (Rule 14).
    """

    def __init__(self, config: GatewayConfig) -> None:
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Pre-Call Pipeline (Rule 2) ───────────────────────────────

    async def pre_call_pipeline(
        self,
        aid_token: str,
        tool_name: str,
        arguments: dict[str, Any],
        server_url: str,
        trace_id: str,
    ) -> TrustPipelineResult:
        """
        Execute pre-call trust pipeline:
          1. M1 — Verify AID
          2. M2 — Check authority
          3. M4 — Filter MNPI from request

        If ANY step fails → DENIED (Rule 12).
        Each step adds to provenance chain (Rule 11).
        """
        chain: list[ProvenanceEntry] = []

        with _tracer.start_as_current_span(
            "pre_call_pipeline",
            attributes={"m6.tool_name": tool_name, "m6.server_url": server_url, "m6.trace_id": trace_id},
        ) as pipeline_span:

            # ── Stage 1: M1 Identity Verification ────────────────────
            with _tracer.start_as_current_span(
                "m1_verify_identity",
                attributes={"m6.stage": "identity_verification", "m6.module": "m1"},
            ) as m1_span:
                t0 = time.monotonic()
                try:
                    claims = await self._verify_identity(aid_token)
                except Exception as e:
                    m1_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    m1_span.set_attribute("m6.passed", False)
                    logger.error("M1 identity verification failed: %s", str(e))
                    return TrustPipelineResult(
                        passed=False,
                        stage_failed=PipelineStage.identity_verification,
                        reason=f"Identity verification failed: {str(e)}",
                        provenance_chain=chain,
                    )

                if not claims.get("valid", False):
                    reason = claims.get("reason", "AID verification failed")
                    m1_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    m1_span.set_attribute("m6.passed", False)
                    logger.warning("M1 denied: %s", reason)
                    return TrustPipelineResult(
                        passed=False,
                        stage_failed=PipelineStage.identity_verification,
                        reason=reason,
                        provenance_chain=chain,
                    )

                m1_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                m1_span.set_attribute("m6.passed", True)

            _add_provenance(
                chain, PipelineStage.identity_verification, "m1",
                {"aid_token_hash": _hash_payload(aid_token), "valid": True},
            )

            # ── Stage 2: M2 Authority Check ──────────────────────────
            aid_claims = claims.get("claims", {})
            with _tracer.start_as_current_span(
                "m2_check_authority",
                attributes={"m6.stage": "authority_check", "m6.module": "m2"},
            ) as m2_span:
                t0 = time.monotonic()
                try:
                    authority = await self._check_authority(aid_claims, tool_name, server_url)
                except Exception as e:
                    m2_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    m2_span.set_attribute("m6.passed", False)
                    logger.error("M2 authority check failed: %s", str(e))
                    return TrustPipelineResult(
                        passed=False,
                        stage_failed=PipelineStage.authority_check,
                        reason=f"Authority check failed: {str(e)}",
                        provenance_chain=chain,
                    )

                decision = authority.get("decision", "DENY")
                if decision != "ALLOW":
                    reason = authority.get("reason", "Authority denied")
                    m2_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    m2_span.set_attribute("m6.passed", False)
                    logger.warning("M2 denied: %s (decision=%s)", reason, decision)
                    return TrustPipelineResult(
                        passed=False,
                        stage_failed=PipelineStage.authority_check,
                        reason=reason,
                        provenance_chain=chain,
                    )

                m2_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                m2_span.set_attribute("m6.passed", True)

            _add_provenance(
                chain, PipelineStage.authority_check, "m2",
                {"decision": "ALLOW", "tool": tool_name},
            )

            # ── Stage 3: M4 MNPI Filter Request ──────────────────────
            with _tracer.start_as_current_span(
                "m4_filter_request",
                attributes={"m6.stage": "mnpi_filter_request", "m6.module": "m4"},
            ) as m4_span:
                t0 = time.monotonic()
                try:
                    filter_result = await self._filter_mnpi(
                        data_payload=arguments,
                        claims=aid_claims,
                        direction="request",
                    )
                except Exception as e:
                    m4_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    m4_span.set_attribute("m6.passed", False)
                    logger.error("M4 MNPI filter (request) failed: %s", str(e))
                    return TrustPipelineResult(
                        passed=False,
                        stage_failed=PipelineStage.mnpi_filter_request,
                        reason=f"MNPI filter failed: {str(e)}",
                        provenance_chain=chain,
                    )

                m4_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                m4_span.set_attribute("m6.passed", True)

            filtered_args = filter_result.get("filtered_payload", arguments)
            _add_provenance(
                chain, PipelineStage.mnpi_filter_request, "m4",
                filtered_args,
            )

            pipeline_span.set_attribute("m6.passed", True)

            return TrustPipelineResult(
                passed=True,
                provenance_chain=chain,
                verified_claims=aid_claims,
                filtered_arguments=filtered_args,
            )

    # ── Post-Call Pipeline (Rule 3) ──────────────────────────────

    async def post_call_pipeline(
        self,
        raw_response: Any,
        claims: dict[str, Any],
        tool_name: str,
        server_url: str,
        trace_id: str,
        provenance_chain: list[ProvenanceEntry],
        request_arguments: dict[str, Any],
    ) -> tuple[bool, Any, list[ProvenanceEntry], Optional[str]]:
        """
        Execute post-call trust pipeline:
          1. M7 — Translate vendor response to canonical format
          2. M4 — Filter MNPI from response
          3. MNPI Leakage Scan — 3-layer guardrail
          4. M10 — Write audit log entry

        Returns:
            (passed, filtered_response, provenance_chain, failure_reason)
        """
        chain = provenance_chain

        with _tracer.start_as_current_span(
            "post_call_pipeline",
            attributes={"m6.tool_name": tool_name, "m6.server_url": server_url, "m6.trace_id": trace_id},
        ) as pipeline_span:

            # ── Stage 1: M7 Response Translation ─────────────────────
            with _tracer.start_as_current_span(
                "m7_translate_response",
                attributes={"m6.stage": "response_translate", "m6.module": "m7"},
            ) as m7_span:
                t0 = time.monotonic()
                try:
                    translated = await self._translate_response(raw_response, server_url)
                    _add_provenance(
                        chain, PipelineStage.response_translate, "m7", translated,
                    )
                    m7_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    m7_span.set_attribute("m6.passed", True)
                except Exception as e:
                    m7_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    m7_span.set_attribute("m6.passed", False)
                    logger.error("M7 translation failed: %s", str(e))
                    return False, None, chain, f"Translation failed: {e}"

            # ── Stage 2: M4 MNPI Filter Response ─────────────────────
            with _tracer.start_as_current_span(
                "m4_filter_response",
                attributes={"m6.stage": "mnpi_filter_response", "m6.module": "m4"},
            ) as m4_span:
                t0 = time.monotonic()
                try:
                    filter_result = await self._filter_mnpi(
                        data_payload=translated if isinstance(translated, dict) else {"result": translated},
                        claims=claims,
                        direction="response",
                    )
                except Exception as e:
                    m4_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    m4_span.set_attribute("m6.passed", False)
                    logger.error("M4 MNPI filter (response) failed: %s", str(e))
                    return False, None, chain, f"MNPI filter failed: {str(e)}"

                m4_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                m4_span.set_attribute("m6.passed", True)

            filtered_response = filter_result.get("filtered_payload", translated)
            _add_provenance(
                chain, PipelineStage.mnpi_filter_response, "m4",
                filtered_response,
            )

            # ── Stage 3: MNPI Leakage Scan (Rule 10) ─────────────────
            with _tracer.start_as_current_span(
                "mnpi_leakage_scan",
                attributes={"m6.stage": "leakage_scan", "m6.module": "m6"},
            ) as scan_span:
                t0 = time.monotonic()
                scan_result = scan_output(filtered_response)
                scan_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                scan_span.set_attribute("m6.passed", scan_result.passed)

            _add_provenance(
                chain, PipelineStage.leakage_scan, "m6",
                {"passed": scan_result.passed, "layers": len(scan_result.layers)},
            )

            if not scan_result.passed:
                logger.warning(
                    "MNPI leakage detected: %s", scan_result.blocked_reason,
                )
                # Still write audit log for blocked responses
                await self._safe_audit_log(
                    trace_id=trace_id,
                    claims=claims,
                    tool_name=tool_name,
                    decision="deny",
                    reason=scan_result.blocked_reason or "MNPI leakage detected",
                    provenance_chain=chain,
                    request_arguments=request_arguments,
                )
                return False, None, chain, scan_result.blocked_reason

            # ── Stage 4: M10 Audit Log (Rule 3) ──────────────────────
            with _tracer.start_as_current_span(
                "m10_write_audit",
                attributes={"m6.stage": "audit_log", "m6.module": "m10"},
            ) as m10_span:
                t0 = time.monotonic()
                try:
                    await self._write_audit_log(
                        trace_id=trace_id,
                        claims=claims,
                        tool_name=tool_name,
                        decision="allow",
                        reason="Request completed successfully",
                        provenance_chain=chain,
                        request_arguments=request_arguments,
                        response_data=filtered_response,
                    )
                    m10_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    m10_span.set_attribute("m6.passed", True)
                except Exception as e:
                    # Fail-closed: if audit write fails, response NOT returned
                    m10_span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    m10_span.set_attribute("m6.passed", False)
                    logger.error("M10 audit write failed: %s", str(e))
                    return False, None, chain, f"Audit write failed: {str(e)}"

            _add_provenance(
                chain, PipelineStage.audit_log, "m10",
                {"trace_id": trace_id, "decision": "allow"},
            )

            pipeline_span.set_attribute("m6.passed", True)

            return True, filtered_response, chain, None

    # ── REST Calls to Dependent Modules (Rule 14) ────────────────

    async def _verify_identity(self, aid_token: str) -> dict[str, Any]:
        """Call M1 to verify AID token. REST only, no import."""
        client = await self._get_client()
        url = f"{self.config.m1_base_url.rstrip('/')}/aid/verify"
        resp = await client.post(url, json={"token": aid_token})
        resp.raise_for_status()
        return resp.json()

    async def _check_authority(
        self,
        claims: dict[str, Any],
        action: str,
        server_url: str,
    ) -> dict[str, Any]:
        """Call M2 to check authority. REST only, no import."""
        client = await self._get_client()
        url = f"{self.config.m2_base_url.rstrip('/')}/policy/authority"
        payload = {
            "identity": {
                "actor_type": claims.get("actor_type", "human"),
                "archetype": claims.get("archetype", "tier4_independent_ria"),
                "role": claims.get("role", "advisor"),
                "firm_id": claims.get("firm_id", ""),
                "jurisdiction": claims.get("jurisdiction", "US"),
                "authority_scope": claims.get("authority_scope", []),
                "authority_excludes": claims.get("authority_excludes", []),
                "client_scope": claims.get("client_scope", []),
                "pod_id": claims.get("pod_id"),
            },
            "action": action,
            "context": {"server_url": server_url},
        }
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def _filter_mnpi(
        self,
        data_payload: dict[str, Any],
        claims: dict[str, Any],
        direction: str,
    ) -> dict[str, Any]:
        """Call M4 to filter MNPI fields. REST only, no import."""
        client = await self._get_client()
        url = f"{self.config.m4_base_url.rstrip('/')}/policy/mnpi/filter"
        payload = {
            "data_payload": data_payload,
            "archetype": claims.get("archetype", "tier4_independent_ria"),
            "role": claims.get("role", "advisor"),
            "jurisdiction": claims.get("jurisdiction", "US"),
            "client_scope": claims.get("client_scope", []),
            "pod_id": claims.get("pod_id"),
        }
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def _translate_response(
        self,
        raw_response: Any,
        server_url: str,
    ) -> Any:
        """Call M7 to translate vendor response to canonical format."""
        client = await self._get_client()
        url = f"{self.config.m7_base_url.rstrip('/')}/translate"
        payload = {
            "source": server_url,
            "data": raw_response,
        }
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def _write_audit_log(
        self,
        trace_id: str,
        claims: dict[str, Any],
        tool_name: str,
        decision: str,
        reason: str,
        provenance_chain: list[ProvenanceEntry],
        request_arguments: dict[str, Any],
        response_data: Any = None,
    ) -> dict[str, Any]:
        """Call M10 to write audit log entry. REST only, no import."""
        client = await self._get_client()
        url = f"{self.config.m10_base_url.rstrip('/')}/audit/write"
        payload = {
            "trace_id": trace_id,
            "actor_id": _hash_payload(claims.get("display_name", "unknown")),
            "action": tool_name,
            "module": "m6",
            "decision": decision,
            "reason": reason,
            "input_hash": _hash_payload(request_arguments),
            "output_hash": _hash_payload(response_data or {}),
            "archetype": claims.get("archetype"),
            "role": claims.get("role"),
            "firm_id": claims.get("firm_id", "unknown"),
            "jurisdiction": claims.get("jurisdiction", "US"),
            "provenance_chain": [
                {
                    "stage": e.stage.value,
                    "module": e.module,
                    "hash": e.hash,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in provenance_chain
            ],
        }
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    async def _safe_audit_log(self, **kwargs: Any) -> None:
        """Write audit log, swallowing errors (for denied requests)."""
        try:
            await self._write_audit_log(**kwargs, response_data=None)
        except Exception as e:
            logger.error("Failed to write audit for denied request: %s", str(e))
