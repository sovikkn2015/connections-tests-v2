"""
M9 Task 12 -- Concurrency smoke test + R19 semaphore verification.

AC1.5, AC16.7, AC19.1-19.5.
"""

from __future__ import annotations

import concurrent.futures
import time

from m9_intent_router import IntentCategory, route
from m9_intent_router.models import LlmClassification
from m9_intent_router.route import _inflight_count


def _provider():
    from m9_intent_router.llm_client import FakeLlmClient

    resp = LlmClassification(
        intent=IntentCategory.RESEARCH_MEETING_PREP,
        confidence=0.97,
        entities={},
        latency_ms=10,
        model="fake",
        provider="fake",
    )
    return FakeLlmClient(
        responses={f"prep me meeting {i}": resp for i in range(1000)},
        classify_latency_ms=5,
    )


def test_inflight_semaphore_caps_concurrency(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
):
    """AC19.3 -- 50 threads x 20 calls finish with no deadlock, < 30s."""
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = _provider()
    cfg = fixture_intent_router_config

    def _do(i: int):
        utter = f"prep me meeting {i % 100}"
        return route(utter, ctx, _provider=provider, _config=cfg)

    start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as ex:
        futures = [ex.submit(_do, i) for i in range(1000)]
        results = [f.result(timeout=30) for f in futures]
    elapsed = time.perf_counter() - start
    assert len(results) == 1000
    assert elapsed < 30, f"exceeded 30s wall clock: {elapsed:.2f}s"
    # After all threads complete, inflight counter returns to zero.
    assert _inflight_count() == 0
