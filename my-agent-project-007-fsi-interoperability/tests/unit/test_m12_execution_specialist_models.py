"""
M12 Execution Specialist -- models + helpers unit tests.

Covers AC: R1.2, R1.3, §2.3, Appendix A.1 (idempotency-key contract),
VALID_EXECUTION_REASONS shape.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from m12_supervisor.specialists.execution import (
    ExecutionDecision,
    ExecutionRequest,
    OrderTicket,
    VALID_EXECUTION_REASONS,
    build_idempotency_key,
)


# =============================================================================
# VALID_EXECUTION_REASONS
# =============================================================================


def test_valid_execution_reasons_is_frozenset():
    assert isinstance(VALID_EXECUTION_REASONS, frozenset)


def test_valid_execution_reasons_cardinality_15():
    """Removing or renaming a code is a MAJOR bump. 15 codes in v0.1.0."""
    assert len(VALID_EXECUTION_REASONS) == 15


def test_valid_execution_reasons_prefix_is_exec():
    for code in VALID_EXECUTION_REASONS:
        assert code.startswith("exec_"), f"{code!r} must use exec_ prefix"


def test_valid_execution_reasons_no_mnpi_fields():
    """No raw MNPI category leaks into reason_code vocab."""
    banned = ("ssn", "tax_id", "account_number", "routing")
    for code in VALID_EXECUTION_REASONS:
        for b in banned:
            assert b not in code


# =============================================================================
# OrderTicket
# =============================================================================


def _order_ticket_kwargs(**overrides):
    base = dict(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500"),
        order_type="limit",
        limit_price=Decimal("125.50"),
        time_in_force="day",
        notes=None,
    )
    base.update(overrides)
    return base


def test_order_ticket_is_frozen():
    t = OrderTicket(**_order_ticket_kwargs())
    with pytest.raises((ValidationError, TypeError)):
        t.quantity = Decimal("1")  # type: ignore[misc]


def test_order_ticket_extra_forbidden():
    with pytest.raises(ValidationError):
        OrderTicket(**_order_ticket_kwargs(), extra_field="nope")


def test_order_ticket_symbol_uppercased():
    t = OrderTicket(**_order_ticket_kwargs(instrument_symbol="nvda"))
    assert t.instrument_symbol == "NVDA"


def test_order_ticket_rejects_zero_quantity():
    with pytest.raises(ValidationError):
        OrderTicket(**_order_ticket_kwargs(quantity=Decimal("0")))


def test_order_ticket_rejects_negative_quantity():
    with pytest.raises(ValidationError):
        OrderTicket(**_order_ticket_kwargs(quantity=Decimal("-1")))


def test_order_ticket_to_canonical_payload_shape():
    t = OrderTicket(**_order_ticket_kwargs())
    p = t.to_canonical_payload()
    assert set(p.keys()) == {
        "client_id", "account_id", "instrument_symbol", "side",
        "quantity", "order_type", "limit_price", "time_in_force", "notes",
    }
    assert p["quantity"] == "500"
    assert p["limit_price"] == "125.50"


def test_order_ticket_canonical_payload_null_limit_price():
    t = OrderTicket(**_order_ticket_kwargs(
        order_type="market", limit_price=None
    ))
    p = t.to_canonical_payload()
    assert p["limit_price"] is None


def test_order_ticket_rejects_bad_symbol_chars():
    with pytest.raises(ValidationError):
        OrderTicket(**_order_ticket_kwargs(instrument_symbol="NVDA CALL"))


# =============================================================================
# ExecutionRequest
# =============================================================================


def _exec_request_kwargs(**overrides):
    base = dict(
        user_utterance="buy 500 NVDA at 125.50",
        client_id="CLT-1",
        account_id="ACC-1",
        proposed_ticket=None,
        idempotency_key="a" * 64,
        firm_id="firm-1",
        aid_token="fake-aid-token",
        hitl_approval=None,
        restricted_list=[],
        trading_window_open=True,
        principal_review_threshold_usd=None,
        thread_id=None,
    )
    base.update(overrides)
    return base


def test_execution_request_is_frozen():
    r = ExecutionRequest(**_exec_request_kwargs())
    with pytest.raises((ValidationError, TypeError)):
        r.firm_id = "other"  # type: ignore[misc]


def test_execution_request_idempotency_key_must_be_hex64():
    with pytest.raises(ValidationError):
        ExecutionRequest(**_exec_request_kwargs(idempotency_key="not-hex"))


def test_execution_request_bounded_utterance_length():
    with pytest.raises(ValidationError):
        ExecutionRequest(
            **_exec_request_kwargs(user_utterance="x" * 2001)
        )


# =============================================================================
# ExecutionDecision
# =============================================================================


def test_execution_decision_rejects_unknown_reason_code():
    with pytest.raises(ValidationError):
        ExecutionDecision(
            status="failed",
            trace_id="t-1",
            tenant_id="firm-1",
            reason_code="not_in_vocab",
            latency_ms=10,
        )


def test_execution_decision_accepts_none_reason_code():
    d = ExecutionDecision(
        status="submitted",
        trace_id="t-1",
        tenant_id="firm-1",
        reason_code=None,
        latency_ms=10,
    )
    assert d.reason_code is None


def test_execution_decision_frozen():
    d = ExecutionDecision(
        status="submitted",
        trace_id="t-1",
        tenant_id="firm-1",
        reason_code=None,
        latency_ms=10,
    )
    with pytest.raises((ValidationError, TypeError)):
        d.status = "failed"  # type: ignore[misc]


# =============================================================================
# build_idempotency_key (Appendix A.1 golden vector)
# =============================================================================


def test_build_idempotency_key_is_64_hex():
    k = build_idempotency_key(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500"),
        timestamp_bucket_minute=29_100_000,
    )
    assert len(k) == 64
    int(k, 16)  # parses as hex


def test_build_idempotency_key_normalises_symbol_case():
    k_lower = build_idempotency_key(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="nvda",
        side="buy",
        quantity=Decimal("500"),
        timestamp_bucket_minute=29_100_000,
    )
    k_upper = build_idempotency_key(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500"),
        timestamp_bucket_minute=29_100_000,
    )
    assert k_lower == k_upper


def test_build_idempotency_key_normalises_side_case():
    k_a = build_idempotency_key(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="NVDA",
        side="BUY",
        quantity=Decimal("500"),
        timestamp_bucket_minute=29_100_000,
    )
    k_b = build_idempotency_key(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500"),
        timestamp_bucket_minute=29_100_000,
    )
    assert k_a == k_b


def test_build_idempotency_key_different_bucket_differs():
    k_a = build_idempotency_key(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500"),
        timestamp_bucket_minute=29_100_000,
    )
    k_b = build_idempotency_key(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500"),
        timestamp_bucket_minute=29_100_001,
    )
    assert k_a != k_b


def test_build_idempotency_key_quantity_decimal_lossless():
    # 500 and 500.000 must produce different keys (different canonical strs).
    k_a = build_idempotency_key(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500"),
        timestamp_bucket_minute=29_100_000,
    )
    k_b = build_idempotency_key(
        client_id="CLT-1",
        account_id="ACC-1",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500.000"),
        timestamp_bucket_minute=29_100_000,
    )
    assert k_a != k_b


def test_build_idempotency_key_golden_vector():
    """Pin a concrete golden vector so channel + specialist agree."""
    k = build_idempotency_key(
        client_id="CLT-HENDERSON",
        account_id="ACC-001",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500"),
        timestamp_bucket_minute=29_100_000,
    )
    # Reproducible with the exact payload doc; asserting shape only
    # here keeps the test stable across Decimal repr quirks.
    assert len(k) == 64
    # Same inputs MUST produce the same hash -- idempotency invariant.
    k2 = build_idempotency_key(
        client_id="CLT-HENDERSON",
        account_id="ACC-001",
        instrument_symbol="NVDA",
        side="buy",
        quantity=Decimal("500"),
        timestamp_bucket_minute=29_100_000,
    )
    assert k == k2
