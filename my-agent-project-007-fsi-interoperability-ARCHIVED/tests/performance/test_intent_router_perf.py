"""
Performance Tests — M9 Intent Classification.

Benchmarks the deterministic fast-path of the intent router:
  - Taxonomy keyword matching: p99 < 1ms
  - Confidence threshold routing: p99 < 1ms

These test the regex/keyword matching path only (no LLM fallback).
The deterministic path handles >95% of production traffic.

Uses time.perf_counter_ns() for nanosecond precision.
No external benchmarking libraries — just pytest + time.
"""

from __future__ import annotations

import time

import pytest

from conftest import percentile, print_latency_stats

# M9 uses bare imports (from models import ...) so we need m9 dir on sys.path
# This is handled by conftest.py which adds m9-intent-router to sys.path
from taxonomy import KEYWORD_PATTERNS, extract_params
from models import ConfidenceTier, FSIIntent, IntentCategory


def _resolve_tier(confidence: float) -> ConfidenceTier:
    """Map confidence score to routing tier (mirrors router.py logic)."""
    if confidence > 0.95:
        return ConfidenceTier.direct
    if confidence >= 0.80:
        return ConfidenceTier.plan
    return ConfidenceTier.clarify


def _deterministic_classify(text: str) -> FSIIntent | None:
    """
    Deterministic regex/keyword matching (mirrors IntentRouter logic).
    Extracted here to benchmark without async overhead.
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


# ── Test inputs covering all 5 intent categories ─────────────────

_TAXONOMY_TEST_INPUTS: list[tuple[str, IntentCategory, str]] = [
    # research
    ("Research AAPL earnings and growth outlook", IntentCategory.research, "security_analysis"),
    ("Deep dive into MSFT financials", IntentCategory.research, "security_analysis"),
    ("Market outlook for Q2 2025", IntentCategory.research, "market_overview"),
    ("SEC 10-K filing for TSLA", IntentCategory.research, "sec_filing_analysis"),
    ("Earnings for GOOGL this quarter", IntentCategory.research, "earnings_analysis"),
    # client
    ("Prepare for meeting with Johnson", IntentCategory.client, "prep_meeting"),
    ("Client summary for Williams", IntentCategory.client, "client_summary"),
    ("Portfolio review for Davis", IntentCategory.client, "portfolio_review"),
    ("Meeting prep for Thompson", IntentCategory.client, "prep_meeting"),
    # compliance
    ("Check restricted list for NVDA", IntentCategory.compliance, "restricted_list_check"),
    ("Run compliance check", IntentCategory.compliance, "general_check"),
    ("Suitability check for Anderson", IntentCategory.compliance, "suitability_check"),
    ("Concentration check for AMZN", IntentCategory.compliance, "concentration_check"),
    ("Check trading window status", IntentCategory.compliance, "trading_window_check"),
    # execution
    ("Buy 100 shares of AAPL", IntentCategory.execution, "order_draft"),
    ("Sell 500 shares of TSLA", IntentCategory.execution, "order_draft"),
    ("Rebalance portfolio for Martinez", IntentCategory.execution, "rebalance"),
    ("Buy MSFT for the growth portfolio", IntentCategory.execution, "order_draft"),
    # onboarding
    ("Start KYC for new client Robinson", IntentCategory.onboarding, "kyc_initiation"),
    ("Open new account for Garcia", IntentCategory.onboarding, "account_opening"),
    ("Begin onboarding for Lee", IntentCategory.onboarding, "general_onboarding"),
]


# ═══════════════════════════════════════════════════════════════════
# TAXONOMY LOOKUP BENCHMARKS
# ═══════════════════════════════════════════════════════════════════


class TestIntentRouterPerf:
    """Intent classification must complete within latency budgets."""

    def test_taxonomy_lookup_latency(self) -> None:
        """
        Run taxonomy matching 1000 times across all intent categories.
        Assert p99 < 1ms.

        Cycles through all test inputs to exercise every regex pattern.
        """
        latencies_ms: list[float] = []
        num_inputs = len(_TAXONOMY_TEST_INPUTS)

        # Warm up
        for text, _, _ in _TAXONOMY_TEST_INPUTS:
            _deterministic_classify(text)

        for i in range(1000):
            text, expected_cat, expected_action = (
                _TAXONOMY_TEST_INPUTS[i % num_inputs]
            )

            start = time.perf_counter_ns()
            result = _deterministic_classify(text)
            elapsed_ns = time.perf_counter_ns() - start
            latencies_ms.append(elapsed_ns / 1_000_000)

            # Functional sanity
            assert result is not None, f"No match for: {text}"
            assert result.category == expected_cat, (
                f"Expected {expected_cat}, got {result.category} for: {text}"
            )
            assert result.action == expected_action, (
                f"Expected {expected_action}, got {result.action} "
                f"for: {text}"
            )

        p99 = percentile(latencies_ms, 99)
        print_latency_stats("Taxonomy lookup (1000 runs)", latencies_ms)

        assert p99 < 1.0, (
            f"Taxonomy lookup p99={p99:.3f}ms exceeds 1ms budget"
        )

    def test_confidence_routing_latency(self) -> None:
        """
        Run confidence threshold routing 1000 times. Assert p99 < 1ms.

        Tests the full classify + resolve tier path. All deterministic
        matches should route to 'direct' tier (confidence > 0.95).
        """
        latencies_ms: list[float] = []
        num_inputs = len(_TAXONOMY_TEST_INPUTS)

        # Warm up
        for text, _, _ in _TAXONOMY_TEST_INPUTS:
            result = _deterministic_classify(text)
            if result:
                _resolve_tier(result.confidence)

        for i in range(1000):
            text, expected_cat, _ = _TAXONOMY_TEST_INPUTS[i % num_inputs]

            start = time.perf_counter_ns()
            result = _deterministic_classify(text)
            assert result is not None
            tier = _resolve_tier(result.confidence)
            elapsed_ns = time.perf_counter_ns() - start
            latencies_ms.append(elapsed_ns / 1_000_000)

            # All deterministic matches have confidence >= 0.96
            assert tier == ConfidenceTier.direct, (
                f"Expected direct tier, got {tier} "
                f"(confidence={result.confidence}) for: {text}"
            )

        p99 = percentile(latencies_ms, 99)
        print_latency_stats("Confidence routing (1000 runs)", latencies_ms)

        assert p99 < 1.0, (
            f"Confidence routing p99={p99:.3f}ms exceeds 1ms budget"
        )
