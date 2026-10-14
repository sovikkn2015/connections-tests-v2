"""
M6 MNPI Leakage Scan — 3-Layer Guardrail (ARCH-06 Gap 6, Rule 10).

Applied to every outbound response before returning to caller.

Layer A: Regex pattern matching (<10ms) — Phase 1 IMPLEMENTED
Layer B: NER (Named Entity Recognition) — Phase 2 STUB (returns pass)
Layer C: Haiku LLM classification — Phase 3 STUB (returns pass)

If Layer A detects MNPI leakage, response is BLOCKED. Fail-closed.
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

from .models import LayerResult, LeakageLayer, LeakageScanResult

logger = logging.getLogger("m6.leakage_scan")


# ── Startup Guard — Layer Readiness Check ────────────────────────


def check_layer_readiness() -> None:
    """
    Verify leakage scan layer readiness at startup.

    Logs WARNING for any stub layer (not_implemented=True).
    If env var REQUIRE_ALL_LEAKAGE_LAYERS is "true" and any layer
    is not implemented, raises RuntimeError (fail-closed at startup).
    """
    # Probe each layer with empty text to inspect not_implemented flags
    layer_b = _scan_layer_b("")
    layer_c = _scan_layer_c("")

    stubs: list[str] = []
    if layer_b.not_implemented:
        stubs.append(layer_b.layer.value)
        logger.warning(
            "Leakage scan Layer B (NER) is a stub (not_implemented=True). "
            "Phase 2 implementation required for full MNPI coverage."
        )
    if layer_c.not_implemented:
        stubs.append(layer_c.layer.value)
        logger.warning(
            "Leakage scan Layer C (Haiku LLM) is a stub (not_implemented=True). "
            "Phase 3 implementation required for full MNPI coverage."
        )

    require_all = os.environ.get("REQUIRE_ALL_LEAKAGE_LAYERS", "").lower() == "true"
    if require_all and stubs:
        raise RuntimeError(
            f"REQUIRE_ALL_LEAKAGE_LAYERS is set but these layers are stubs: "
            f"{', '.join(stubs)}. Cannot start in strict mode."
        )

    if not stubs:
        logger.info("All leakage scan layers are fully implemented.")
    else:
        logger.info(
            "Leakage scan running with %d stub layer(s): %s. "
            "Layer A (regex) is active and enforcing.",
            len(stubs),
            ", ".join(stubs),
        )


# ── Layer A: Regex Patterns (<10ms budget) ───────────────────────
# Patterns for common MNPI / PII that must never leak to clients.

_MNPI_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # SSN: 123-45-6789 or 123456789
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("ssn_no_dash", re.compile(r"\b\d{9}\b")),
    # Account numbers: 8-17 digit sequences (common custodian format)
    ("account_number", re.compile(r"\b\d{8,17}\b")),
    # Date of birth patterns: MM/DD/YYYY, MM-DD-YYYY, YYYY-MM-DD
    ("dob_us", re.compile(r"\b(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12]\d|3[01])[/-](?:19|20)\d{2}\b")),
    ("dob_iso", re.compile(r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])\b")),
    # Credit card: 13-19 digits with optional dashes/spaces
    ("credit_card", re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{1,7}\b")),
    # Routing number: 9 digits starting with 0-3
    ("routing_number", re.compile(r"\b[0-3]\d{8}\b")),
    # ITIN: 9XX-XX-XXXX where X is digit
    ("itin", re.compile(r"\b9\d{2}-\d{2}-\d{4}\b")),
    # EIN: XX-XXXXXXX
    ("ein", re.compile(r"\b\d{2}-\d{7}\b")),
    # Known MNPI keywords in context
    ("mnpi_keyword", re.compile(
        r"\b(?:material\s+non-?public|insider\s+(?:information|trading)|"
        r"pre-?announcement|earnings\s+(?:surprise|leak)|"
        r"merger\s+(?:target|acquisition)|tender\s+offer)\b",
        re.IGNORECASE,
    )),
]


def _extract_text(data: Any) -> str:
    """Recursively extract all string values from a data structure."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        return " ".join(_extract_text(v) for v in data.values())
    if isinstance(data, (list, tuple)):
        return " ".join(_extract_text(item) for item in data)
    return str(data) if data is not None else ""


def _scan_layer_a(text: str) -> LayerResult:
    """
    Layer A: Regex pattern matching.
    Budget: <10ms. Scans for SSN, account numbers, DOB, known MNPI patterns.
    """
    start = time.perf_counter()
    detections: list[str] = []

    for pattern_name, pattern in _MNPI_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            # Log pattern name + count, never the actual matched value
            detections.append(f"{pattern_name}:{len(matches)}")

    elapsed_ms = (time.perf_counter() - start) * 1000

    return LayerResult(
        layer=LeakageLayer.layer_a_regex,
        passed=len(detections) == 0,
        detections=detections,
        not_implemented=False,
        latency_ms=elapsed_ms,
    )


def _scan_layer_b(text: str) -> LayerResult:
    """
    Layer B: NER (Named Entity Recognition).
    Phase 2 STUB — returns pass with not_implemented flag.
    """
    return LayerResult(
        layer=LeakageLayer.layer_b_ner,
        passed=True,
        detections=[],
        not_implemented=True,
        latency_ms=0.0,
    )


def _scan_layer_c(text: str) -> LayerResult:
    """
    Layer C: Haiku LLM classification for MNPI content.

    Activated when LEAKAGE_SCAN_LAYER_C_ENABLED=true and Bedrock is available.
    Uses Bedrock Claude Haiku to classify text for MNPI content.
    Fail-closed: if Bedrock unavailable → passed=False (Rule 2).

    When disabled (default): returns stub with not_implemented=True.
    """
    enabled = os.environ.get("LEAKAGE_SCAN_LAYER_C_ENABLED", "false").lower() == "true"

    if not enabled:
        return LayerResult(
            layer=LeakageLayer.layer_c_llm,
            passed=True,
            detections=[],
            not_implemented=True,
            latency_ms=0.0,
        )

    start = time.perf_counter()

    try:
        import boto3
        import json as _json
    except ImportError:
        logger.error("boto3 required for Layer C LLM scan but not installed")
        elapsed_ms = (time.perf_counter() - start) * 1000
        return LayerResult(
            layer=LeakageLayer.layer_c_llm,
            passed=False,
            detections=["llm_classifier:boto3_unavailable"],
            not_implemented=False,
            latency_ms=elapsed_ms,
        )

    try:
        bedrock_region = os.environ.get("AWS_BEDROCK_REGION", "us-east-1")
        client = boto3.client("bedrock-runtime", region_name=bedrock_region)

        # Truncate text to avoid excessive token usage (Haiku context)
        scan_text = text[:4000] if len(text) > 4000 else text

        prompt = (
            "Does the following text contain Material Non-Public Information "
            "(MNPI) such as undisclosed earnings, pending mergers, insider "
            "trading details, or non-public financial data? Respond with "
            "only YES or NO.\n\n"
            f"Text: {scan_text}"
        )

        model_id = os.environ.get(
            "LEAKAGE_SCAN_LAYER_C_MODEL",
            "anthropic.claude-3-haiku-20240307-v1:0",
        )

        body = _json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 10,
            "temperature": 0.0,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        })

        response = client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )

        response_body = _json.loads(response["body"].read())
        answer = ""
        if response_body.get("content"):
            answer = response_body["content"][0].get("text", "").strip().upper()

        elapsed_ms = (time.perf_counter() - start) * 1000

        if answer.startswith("YES"):
            logger.warning(
                "Layer C LLM detected MNPI content (%.1fms)", elapsed_ms,
            )
            return LayerResult(
                layer=LeakageLayer.layer_c_llm,
                passed=False,
                detections=["llm_classifier:mnpi_detected"],
                not_implemented=False,
                latency_ms=elapsed_ms,
            )

        if answer.startswith("NO"):
            return LayerResult(
                layer=LeakageLayer.layer_c_llm,
                passed=True,
                detections=[],
                not_implemented=False,
                latency_ms=elapsed_ms,
            )

        # Ambiguous response — fail-closed (Rule 2)
        logger.warning(
            "Layer C LLM returned ambiguous response: %s — fail-closed",
            answer[:50],
        )
        return LayerResult(
            layer=LeakageLayer.layer_c_llm,
            passed=False,
            detections=["llm_classifier:ambiguous_response"],
            not_implemented=False,
            latency_ms=elapsed_ms,
        )

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        # Fail-closed: Bedrock unavailable → DENY (Rule 2)
        logger.error(
            "Layer C Bedrock call failed — fail-closed: %s (%.1fms)",
            exc, elapsed_ms,
        )
        return LayerResult(
            layer=LeakageLayer.layer_c_llm,
            passed=False,
            detections=["llm_classifier:bedrock_unavailable"],
            not_implemented=False,
            latency_ms=elapsed_ms,
        )


def scan_output(data: Any) -> LeakageScanResult:
    """
    Run the 3-layer MNPI leakage scan on outbound data.

    Phase 1: Only Layer A (regex) is active.
    If Layer A detects leakage → response BLOCKED (fail-closed).
    Layers B and C are stubs returning pass.

    Args:
        data: Response data to scan (dict, list, str, or any JSON-serializable).

    Returns:
        LeakageScanResult with overall pass/fail and per-layer details.
    """
    text = _extract_text(data)

    layer_a = _scan_layer_a(text)
    layer_b = _scan_layer_b(text)
    layer_c = _scan_layer_c(text)

    layers = [layer_a, layer_b, layer_c]
    all_passed = all(layer.passed for layer in layers)

    blocked_reason = None
    if not all_passed:
        failed_layers = [l for l in layers if not l.passed]
        blocked_reason = (
            f"MNPI leakage detected by: "
            f"{', '.join(l.layer.value for l in failed_layers)}"
        )

    return LeakageScanResult(
        passed=all_passed,
        layers=layers,
        blocked_reason=blocked_reason,
    )
