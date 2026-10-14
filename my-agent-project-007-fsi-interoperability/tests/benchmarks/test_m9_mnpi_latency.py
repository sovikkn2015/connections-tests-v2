"""
M9 Task 14 -- MNPI short-circuit latency benchmark.

AC8.5: route() returns in <20ms for MNPI-suspected utterances.
"""

from __future__ import annotations

import time

from m9_intent_router import IntentCategory, route
from m9_intent_router.llm_client import FakeLlmClient


def test_mnpi_short_circuit_under_20ms(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
):
    """AC8.5 -- MNPI hit returns in < 20ms (500 iterations p99)."""
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = FakeLlmClient()  # empty -- should NEVER be called
    cfg = fixture_intent_router_config
    utter = "wire $50k to routing 021000021 account 1234567890"

    latencies = []
    for _ in range(500):
        t0 = time.perf_counter()
        d = route(utter, ctx, _provider=provider, _config=cfg)
        latencies.append((time.perf_counter() - t0) * 1000)
        assert d.reason_code == "mnpi_shape_suspected"
        assert d.intent == IntentCategory.ESCALATE_TO_HUMAN

    latencies.sort()
    p99 = latencies[int(len(latencies) * 0.99)]
    assert p99 < 20, f"MNPI short-circuit p99={p99:.2f}ms exceeds 20ms budget"
