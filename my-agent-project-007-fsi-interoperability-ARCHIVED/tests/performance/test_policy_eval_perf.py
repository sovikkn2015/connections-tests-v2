"""
Performance Tests — Local OPA Policy Evaluator (M2/M4).

Benchmarks the in-memory fallback evaluator from policy_client.py:
  - Authority evaluation: p99 < 5ms
  - MNPI filter evaluation: p99 < 5ms
  - Pod isolation (Tier 5 HF): p99 < 5ms
  - Client scope with 100 clients: p99 < 10ms

These are the local evaluators that mirror OPA/Rego logic.
Production uses OPA server; these benchmarks validate the
in-memory path used for dev/test and as a fallback.

Uses time.perf_counter_ns() for nanosecond precision.
No external benchmarking libraries — just pytest + time.
"""

from __future__ import annotations

import time

import pytest

from conftest import percentile, print_latency_stats
from m2_m4_policy_engine.models import (
    Archetype,
    AuthorityDecision,
    IdentityContext,
    MnpiFilterInput,
    PolicyInput,
    Role,
)
from m2_m4_policy_engine.policy_client import (
    evaluate_authority_local,
    evaluate_mnpi_filter_local,
)


# ── Shared identity fixtures ─────────────────────────────────────


def _ria_advisor_identity() -> IdentityContext:
    """Standard Tier 4 RIA advisor identity."""
    return IdentityContext(
        actor_type="human",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        firm_id="ria-firm-001",
        jurisdiction="US",
        authority_scope=["client.*", "portfolio.*", "research.*"],
        authority_excludes=["order.submit"],
        client_scope=["CLT-10001", "CLT-10002", "CLT-10003"],
    )


def _hf_pm_identity(pod_id: str = "pod-alpha") -> IdentityContext:
    """Tier 5 Hedge Fund portfolio manager with pod isolation."""
    return IdentityContext(
        actor_type="human",
        archetype=Archetype.tier5_hedge_fund,
        role=Role.portfolio_manager,
        firm_id="hf-firm-001",
        jurisdiction="US",
        authority_scope=["portfolio.*", "research.*", "order.*"],
        authority_excludes=[],
        client_scope=[],
        pod_id=pod_id,
    )


# ═══════════════════════════════════════════════════════════════════
# AUTHORITY EVALUATION BENCHMARKS
# ═══════════════════════════════════════════════════════════════════


class TestAuthorityEvalPerf:
    """Authority evaluation must complete within latency budgets."""

    def test_authority_eval_latency(self) -> None:
        """
        Run evaluate_authority_local 1000 times with a standard
        RIA advisor identity. Assert p99 < 5ms.
        """
        identity = _ria_advisor_identity()
        policy_input = PolicyInput(
            identity=identity,
            action="client.read",
            context={"client_id": "CLT-10001"},
        )

        latencies_ms: list[float] = []

        # Warm up
        for _ in range(10):
            evaluate_authority_local(policy_input)

        for _ in range(1000):
            start = time.perf_counter_ns()
            result = evaluate_authority_local(policy_input)
            elapsed_ns = time.perf_counter_ns() - start
            latencies_ms.append(elapsed_ns / 1_000_000)

            assert result.decision == AuthorityDecision.ALLOW

        p99 = percentile(latencies_ms, 99)
        print_latency_stats("Authority eval — standard RIA (1000 runs)", latencies_ms)

        assert p99 < 5.0, (
            f"Authority eval p99={p99:.3f}ms exceeds 5ms budget"
        )

    def test_authority_eval_with_pod_isolation(self) -> None:
        """
        Tier 5 HF pod isolation check 1000 times. Assert p99 < 5ms.

        Pod isolation adds an extra comparison (pod_id != target_pod_id)
        but should not meaningfully increase latency.
        """
        identity = _hf_pm_identity(pod_id="pod-alpha")
        # Same pod — should ALLOW
        policy_input_same = PolicyInput(
            identity=identity,
            action="portfolio.read",
            context={"target_pod_id": "pod-alpha"},
        )
        # Different pod — should DENY
        policy_input_cross = PolicyInput(
            identity=identity,
            action="portfolio.read",
            context={"target_pod_id": "pod-beta"},
        )

        latencies_ms: list[float] = []

        # Warm up
        for _ in range(10):
            evaluate_authority_local(policy_input_same)
            evaluate_authority_local(policy_input_cross)

        for i in range(1000):
            # Alternate between same-pod and cross-pod
            inp = policy_input_same if i % 2 == 0 else policy_input_cross
            expected = (
                AuthorityDecision.ALLOW if i % 2 == 0
                else AuthorityDecision.DENY
            )

            start = time.perf_counter_ns()
            result = evaluate_authority_local(inp)
            elapsed_ns = time.perf_counter_ns() - start
            latencies_ms.append(elapsed_ns / 1_000_000)

            assert result.decision == expected

        p99 = percentile(latencies_ms, 99)
        print_latency_stats("Authority eval — pod isolation (1000 runs)", latencies_ms)

        assert p99 < 5.0, (
            f"Pod isolation eval p99={p99:.3f}ms exceeds 5ms budget"
        )

    def test_authority_eval_with_client_scope(self) -> None:
        """
        Client scope check with 100 clients in scope. Assert p99 < 10ms.

        Large client_scope lists require linear scan. 100 clients is
        a realistic upper bound for a single advisor.
        """
        client_ids = [f"CLT-{i:05d}" for i in range(100)]
        identity = IdentityContext(
            actor_type="human",
            archetype=Archetype.tier4_independent_ria,
            role=Role.advisor,
            firm_id="ria-firm-001",
            jurisdiction="US",
            authority_scope=["client.*", "portfolio.*"],
            authority_excludes=[],
            client_scope=client_ids,
        )

        latencies_ms: list[float] = []

        # Warm up
        for _ in range(10):
            evaluate_authority_local(PolicyInput(
                identity=identity,
                action="client.read",
                context={"client_id": "CLT-00050"},
            ))

        for i in range(1000):
            # Vary the target client to exercise different positions
            target = f"CLT-{i % 100:05d}"
            policy_input = PolicyInput(
                identity=identity,
                action="client.read",
                context={"client_id": target},
            )

            start = time.perf_counter_ns()
            result = evaluate_authority_local(policy_input)
            elapsed_ns = time.perf_counter_ns() - start
            latencies_ms.append(elapsed_ns / 1_000_000)

            assert result.decision == AuthorityDecision.ALLOW

        p99 = percentile(latencies_ms, 99)
        print_latency_stats(
            "Authority eval — 100-client scope (1000 runs)", latencies_ms,
        )

        assert p99 < 10.0, (
            f"Client scope eval p99={p99:.3f}ms exceeds 10ms budget"
        )


# ═══════════════════════════════════════════════════════════════════
# MNPI FILTER EVALUATION BENCHMARKS
# ═══════════════════════════════════════════════════════════════════


class TestMnpiFilterPerf:
    """MNPI filter evaluation must complete within latency budgets."""

    def test_mnpi_filter_latency(self) -> None:
        """
        Run evaluate_mnpi_filter_local 1000 times with a realistic
        client data payload. Assert p99 < 5ms.
        """
        filter_input = MnpiFilterInput(
            data_payload={
                "client_id": "CLT-10001",
                "first_name": "Jane",
                "last_name": "Smith",
                "ssn": "REDACTED-TEST",
                "dob": "REDACTED-TEST",
                "email": "test@example.com",
                "phone": "+1-555-000-0000",
                "tax_id": "REDACTED-TEST",
                "account_value": "$1,250,000",
                "holdings": "AAPL: 500 shares",
                "risk_tolerance": "moderate",
                "investment_objective": "growth",
                "kyc_status": "verified",
                "last_review": "2024-11-15",
                "benchmark": "S&P 500",
            },
            archetype=Archetype.tier4_independent_ria,
            role=Role.advisor,
            jurisdiction="US",
            client_scope=["CLT-10001"],
            target_client_id="CLT-10001",
        )

        latencies_ms: list[float] = []

        # Warm up
        for _ in range(10):
            evaluate_mnpi_filter_local(filter_input)

        for _ in range(1000):
            start = time.perf_counter_ns()
            result = evaluate_mnpi_filter_local(filter_input)
            elapsed_ns = time.perf_counter_ns() - start
            latencies_ms.append(elapsed_ns / 1_000_000)

            # PII fields should be stripped for advisor role
            assert "ssn" not in result.filtered_payload
            assert "dob" not in result.filtered_payload
            assert "email" not in result.filtered_payload

        p99 = percentile(latencies_ms, 99)
        print_latency_stats("MNPI filter — standard payload (1000 runs)", latencies_ms)

        assert p99 < 5.0, (
            f"MNPI filter p99={p99:.3f}ms exceeds 5ms budget"
        )
