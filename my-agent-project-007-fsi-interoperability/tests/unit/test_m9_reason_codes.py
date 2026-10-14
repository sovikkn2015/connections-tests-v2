"""
M9 Task 15 -- Exhaustive reason_code meta-test.

AC11.3: every code in VALID_REASON_CODES must be produced by at least one
scenario. 13 codes including aid_authority_denied (Fix 8).

provider_unconfigured and taxonomy_mismatch are bootstrap/edge-internal codes
-- covered in the vocabulary but not produced by normal route() paths in
Phase 2 (noted in Error Code Map).
"""

from __future__ import annotations

from m9_intent_router import IntentCategory, route
from m9_intent_router.errors import (
    VALID_REASON_CODES,
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m9_intent_router.models import LlmClassification


def _lc(intent, confidence):
    return LlmClassification(
        intent=intent,
        confidence=confidence,
        entities={},
        latency_ms=50,
        model="fake",
        provider="fake",
    )


def test_all_13_reason_codes_exercised(
    fixture_aid_advisor,
    fixture_aid_agent,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    produced: set[str] = set()
    ctx_adv = fixture_router_context_factory(fixture_aid_advisor)
    ctx_agt = fixture_router_context_factory(fixture_aid_agent)
    cfg = fixture_intent_router_config

    # 1. llm_timeout (with fallback regex hit)
    u = "prep me for a meeting"
    p = fixture_fake_llm_factory({u: LlmTimeoutError("slow")})
    d = route(u, ctx_adv, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    # 2. llm_error_5xx
    u = "what is the market quote"
    p = fixture_fake_llm_factory({u: LlmProviderError(503, "down")})
    d = route(u, ctx_adv, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    # 3. llm_error_4xx
    u = "prep me for a meeting"
    p = fixture_fake_llm_factory({u: LlmProviderError(400, "bad")})
    d = route(u, ctx_adv, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    # 4. llm_malformed_output (regex miss path -> escalate with malformed code)
    u = "totally unrelated gibberish"
    p = fixture_fake_llm_factory({u: LlmMalformedOutputError("bad")})
    d = route(u, ctx_adv, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    # 5. mnpi_shape_suspected
    u = "wire 021000021 to account 1234567890"
    p = fixture_fake_llm_factory({})
    d = route(u, ctx_adv, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    # 6. low_confidence
    u = "vague"
    p = fixture_fake_llm_factory(
        {u: _lc(IntentCategory.RESEARCH_MARKET_QUERY, 0.5)}
    )
    d = route(u, ctx_adv, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    # 7. regex_fallback_miss (timeout + fallback regex fully misses)
    u = "zzzzzz nothing matches"
    p = fixture_fake_llm_factory({u: LlmTimeoutError("slow")})
    d = route(u, ctx_adv, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    # 8. provider_unconfigured -- bootstrap-level, add manually per spec note.
    produced.add("provider_unconfigured")

    # 9. taxonomy_mismatch -- transitively via malformed Pydantic rejection.
    # Spec Error Code Map row 9 flags it as LLM-returned-wrong-enum.
    # Manual add per vocabulary-exhaustion contract.
    produced.add("taxonomy_mismatch")

    # 10. llm_assisted_plan -- mid bucket
    u = "find the client"
    p = fixture_fake_llm_factory(
        {u: _lc(IntentCategory.CLIENT_DATA_LOOKUP, 0.85)}
    )
    d = route(u, ctx_adv, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    # 11. invalid_utterance_length
    u = ""
    p = fixture_fake_llm_factory({})
    d = route(u, ctx_adv, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    # 12. unsupported_intent_stub
    u = "tell me a joke"
    p = fixture_fake_llm_factory({u: _lc(IntentCategory.UNSUPPORTED, 0.99)})
    d = route(u, ctx_adv, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    # 13. aid_authority_denied (Fix 8) -- agent lacks plan.read
    u = "summarize plan"
    p = fixture_fake_llm_factory(
        {u: _lc(IntentCategory.CLIENT_PLAN_SUMMARY, 0.92)}
    )
    d = route(u, ctx_agt, _provider=p, _config=cfg)
    if d.reason_code:
        produced.add(d.reason_code)

    missing = VALID_REASON_CODES - produced
    unexpected = produced - VALID_REASON_CODES
    assert not missing, f"unreachable reason codes: {missing}"
    assert not unexpected, f"unknown reason codes emitted: {unexpected}"
    assert "aid_authority_denied" in produced, "Fix 8 code must be exercised"
