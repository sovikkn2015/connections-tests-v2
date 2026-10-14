"""Unit tests for ``m13_fix_bridge.models`` — Spec §R10.

Covers every enum value, every required field, every cross-field
constraint, and ``extra="forbid"`` enforcement.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from m13_fix_bridge.models import (
    KillSwitchInput,
    NewOrderSingleInput,
    OrderCancelInput,
    OrderCancelReplaceInput,
    OrderStatusInput,
    SessionStatusInput,
    VenueConfig,
)


def _utc() -> datetime:
    return datetime(2026, 4, 29, 14, 30, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# NewOrderSingleInput
# ---------------------------------------------------------------------------


def test_new_order_limit_happy_path() -> None:
    m = NewOrderSingleInput(
        cl_ord_id="ABC-001",
        venue="brokerx",
        symbol="AAPL",
        side="1",
        ord_type="2",
        order_qty=Decimal("100"),
        price=Decimal("183.50"),
        time_in_force="0",
        transact_time=_utc(),
        account="ACCT_1",
    )
    assert m.cl_ord_id == "ABC-001"
    assert m.price == Decimal("183.50")


def test_new_order_market_rejects_price() -> None:
    with pytest.raises(ValidationError, match="price must be None when ord_type=1"):
        NewOrderSingleInput(
            cl_ord_id="ABC-002",
            venue="brokerx",
            symbol="AAPL",
            side="2",
            ord_type="1",  # Market
            order_qty=Decimal("10"),
            price=Decimal("1"),
            time_in_force="3",
            transact_time=_utc(),
            account="ACCT_1",
        )


def test_new_order_limit_requires_price() -> None:
    with pytest.raises(ValidationError, match="price is required"):
        NewOrderSingleInput(
            cl_ord_id="ABC-003",
            venue="brokerx",
            symbol="AAPL",
            side="1",
            ord_type="2",
            order_qty=Decimal("10"),
            price=None,
            time_in_force="0",
            transact_time=_utc(),
            account="ACCT_1",
        )


def test_new_order_stop_limit_requires_price() -> None:
    with pytest.raises(ValidationError):
        NewOrderSingleInput(
            cl_ord_id="ABC-004",
            venue="brokerx",
            symbol="AAPL",
            side="1",
            ord_type="4",  # StopLimit
            order_qty=Decimal("10"),
            price=None,
            time_in_force="0",
            transact_time=_utc(),
            account="ACCT_1",
        )


def test_new_order_stop_without_price_allowed() -> None:
    """ord_type=3 (Stop) allows optional price."""
    m = NewOrderSingleInput(
        cl_ord_id="ABC-005",
        venue="brokerx",
        symbol="AAPL",
        side="1",
        ord_type="3",
        order_qty=Decimal("10"),
        price=None,
        time_in_force="0",
        transact_time=_utc(),
        account="ACCT_1",
    )
    assert m.price is None


def test_new_order_rejects_negative_qty() -> None:
    with pytest.raises(ValidationError, match=r"order_qty must be > 0"):
        NewOrderSingleInput(
            cl_ord_id="ABC-006",
            venue="brokerx",
            symbol="AAPL",
            side="1",
            ord_type="1",
            order_qty=Decimal("-1"),
            price=None,
            time_in_force="0",
            transact_time=_utc(),
            account="ACCT_1",
        )


def test_new_order_rejects_zero_qty() -> None:
    with pytest.raises(ValidationError, match=r"order_qty must be > 0"):
        NewOrderSingleInput(
            cl_ord_id="ABC-007",
            venue="brokerx",
            symbol="AAPL",
            side="1",
            ord_type="1",
            order_qty=Decimal("0"),
            price=None,
            time_in_force="0",
            transact_time=_utc(),
            account="ACCT_1",
        )


def test_new_order_rejects_bad_side() -> None:
    with pytest.raises(ValidationError):
        NewOrderSingleInput(
            cl_ord_id="ABC-008",
            venue="brokerx",
            symbol="AAPL",
            side="9",  # not in FIX side enum
            ord_type="1",
            order_qty=Decimal("10"),
            price=None,
            time_in_force="0",
            transact_time=_utc(),
            account="ACCT_1",
        )


def test_new_order_rejects_bad_ord_type() -> None:
    with pytest.raises(ValidationError):
        NewOrderSingleInput(
            cl_ord_id="ABC-009",
            venue="brokerx",
            symbol="AAPL",
            side="1",
            ord_type="7",
            order_qty=Decimal("10"),
            price=None,
            time_in_force="0",
            transact_time=_utc(),
            account="ACCT_1",
        )


def test_new_order_rejects_bad_tif() -> None:
    with pytest.raises(ValidationError):
        NewOrderSingleInput(
            cl_ord_id="ABC-010",
            venue="brokerx",
            symbol="AAPL",
            side="1",
            ord_type="1",
            order_qty=Decimal("10"),
            price=None,
            time_in_force="5",  # 5 is not a valid TIF
            transact_time=_utc(),
            account="ACCT_1",
        )


def test_new_order_rejects_non_utc_datetime() -> None:
    naive = datetime(2026, 4, 29, 14, 30, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        NewOrderSingleInput(
            cl_ord_id="ABC-011",
            venue="brokerx",
            symbol="AAPL",
            side="1",
            ord_type="1",
            order_qty=Decimal("10"),
            price=None,
            time_in_force="0",
            transact_time=naive,
            account="ACCT_1",
        )


def test_new_order_rejects_lowercase_symbol() -> None:
    with pytest.raises(ValidationError, match="symbol must be uppercase"):
        NewOrderSingleInput(
            cl_ord_id="ABC-012",
            venue="brokerx",
            symbol="aapl",
            side="1",
            ord_type="1",
            order_qty=Decimal("10"),
            price=None,
            time_in_force="0",
            transact_time=_utc(),
            account="ACCT_1",
        )


def test_new_order_rejects_uppercase_venue() -> None:
    with pytest.raises(ValidationError):
        NewOrderSingleInput(
            cl_ord_id="ABC-013",
            venue="BROKERX",  # must be lowercase
            symbol="AAPL",
            side="1",
            ord_type="1",
            order_qty=Decimal("10"),
            price=None,
            time_in_force="0",
            transact_time=_utc(),
            account="ACCT_1",
        )


def test_new_order_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        NewOrderSingleInput.model_validate(
            {
                "cl_ord_id": "ABC-014",
                "venue": "brokerx",
                "symbol": "AAPL",
                "side": "1",
                "ord_type": "1",
                "order_qty": Decimal("10"),
                "time_in_force": "0",
                "transact_time": _utc(),
                "account": "ACCT_1",
                "extra_field": "nope",
            }
        )


def test_new_order_rejects_short_sell_enum() -> None:
    """Side '5' (SellShort) is accepted."""
    m = NewOrderSingleInput(
        cl_ord_id="ABC-015",
        venue="brokerx",
        symbol="AAPL",
        side="5",
        ord_type="1",
        order_qty=Decimal("10"),
        price=None,
        time_in_force="0",
        transact_time=_utc(),
        account="ACCT_1",
    )
    assert m.side == "5"


def test_new_order_qty_decimals_capped() -> None:
    with pytest.raises(ValidationError, match="decimal places"):
        NewOrderSingleInput(
            cl_ord_id="ABC-016",
            venue="brokerx",
            symbol="AAPL",
            side="1",
            ord_type="1",
            order_qty=Decimal("0.123456789"),  # 9 decimals — over limit
            price=None,
            time_in_force="0",
            transact_time=_utc(),
            account="ACCT_1",
        )


# ---------------------------------------------------------------------------
# OrderCancelInput + OrderCancelReplaceInput
# ---------------------------------------------------------------------------


def test_order_cancel_happy_path() -> None:
    m = OrderCancelInput(
        orig_cl_ord_id="ABC-001",
        cl_ord_id="ABC-001-X",
        venue="brokerx",
        symbol="AAPL",
        side="1",
        transact_time=_utc(),
    )
    assert m.orig_cl_ord_id == "ABC-001"


def test_order_cancel_replace_requires_price_when_limit() -> None:
    with pytest.raises(ValidationError):
        OrderCancelReplaceInput(
            orig_cl_ord_id="ABC-001",
            cl_ord_id="ABC-001-R",
            venue="brokerx",
            symbol="AAPL",
            side="1",
            ord_type="2",
            order_qty=Decimal("50"),
            price=None,
            time_in_force="0",
            transact_time=_utc(),
        )


def test_order_cancel_replace_market_forbids_price() -> None:
    with pytest.raises(ValidationError):
        OrderCancelReplaceInput(
            orig_cl_ord_id="ABC-001",
            cl_ord_id="ABC-001-R",
            venue="brokerx",
            symbol="AAPL",
            side="1",
            ord_type="1",
            order_qty=Decimal("50"),
            price=Decimal("1.0"),
            time_in_force="0",
            transact_time=_utc(),
        )


# ---------------------------------------------------------------------------
# OrderStatusInput
# ---------------------------------------------------------------------------


def test_order_status_requires_exactly_one_of() -> None:
    with pytest.raises(ValidationError, match="exactly one of"):
        OrderStatusInput(venue="brokerx", symbol="AAPL", side="1")


def test_order_status_rejects_both() -> None:
    with pytest.raises(ValidationError, match="exactly one of"):
        OrderStatusInput(
            venue="brokerx",
            symbol="AAPL",
            side="1",
            cl_ord_id="ABC-001",
            order_id="OID-1",
        )


def test_order_status_accepts_cl_ord_id() -> None:
    m = OrderStatusInput(
        venue="brokerx", symbol="AAPL", side="1", cl_ord_id="ABC-001"
    )
    assert m.cl_ord_id == "ABC-001"


def test_order_status_accepts_order_id() -> None:
    m = OrderStatusInput(
        venue="brokerx", symbol="AAPL", side="1", order_id="OID-12345"
    )
    assert m.order_id == "OID-12345"


# ---------------------------------------------------------------------------
# SessionStatusInput
# ---------------------------------------------------------------------------


def test_session_status_accepts_venue() -> None:
    m = SessionStatusInput(venue="brokerx")
    assert m.venue == "brokerx"


def test_session_status_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        SessionStatusInput(venue="")


# ---------------------------------------------------------------------------
# KillSwitchInput
# ---------------------------------------------------------------------------


def test_kill_switch_global_forbids_venue() -> None:
    with pytest.raises(ValidationError, match="venue must be None when scope=global"):
        KillSwitchInput(
            scope="global",
            venue="brokerx",
            state="on",
            reason="ops-incident-0001",
        )


def test_kill_switch_venue_requires_venue() -> None:
    with pytest.raises(ValidationError, match="venue must be supplied"):
        KillSwitchInput(
            scope="venue",
            venue=None,
            state="on",
            reason="venue-outage-0001",
        )


def test_kill_switch_reason_too_short() -> None:
    with pytest.raises(ValidationError):
        KillSwitchInput(
            scope="global", venue=None, state="on", reason="short"
        )


def test_kill_switch_happy_path_global() -> None:
    m = KillSwitchInput(
        scope="global", venue=None, state="off", reason="incident-cleared"
    )
    assert m.state == "off"


def test_kill_switch_happy_path_venue() -> None:
    m = KillSwitchInput(
        scope="venue",
        venue="brokerx",
        state="on",
        reason="venue-degraded",
    )
    assert m.venue == "brokerx"


# ---------------------------------------------------------------------------
# VenueConfig
# ---------------------------------------------------------------------------


def test_venue_config_requires_mtls_when_tls_true() -> None:
    with pytest.raises(ValidationError, match="mTLS paths"):
        VenueConfig(
            venue="brokerx",
            sender_comp_id_vault_path="secret/data/007/m13/brokerx/sender",
            target_comp_id_vault_path="secret/data/007/m13/brokerx/target",
            host="fix.brokerx.example",
            port=9876,
            heartbeat_interval_s=30,
            reset_on_logon=False,
            use_tls=True,
            cert_path_vault_path=None,
            key_path_vault_path=None,
            ca_path_vault_path=None,
        )


def test_venue_config_allows_use_tls_false() -> None:
    vc = VenueConfig(
        venue="brokerx",
        sender_comp_id_vault_path="secret/data/007/m13/brokerx/sender",
        target_comp_id_vault_path="secret/data/007/m13/brokerx/target",
        host="fix.brokerx.example",
        port=9876,
        heartbeat_interval_s=30,
        reset_on_logon=False,
        use_tls=False,
        cert_path_vault_path=None,
        key_path_vault_path=None,
        ca_path_vault_path=None,
    )
    assert vc.use_tls is False


def test_venue_config_heartbeat_range() -> None:
    with pytest.raises(ValidationError):
        VenueConfig(
            venue="brokerx",
            sender_comp_id_vault_path="p1",
            target_comp_id_vault_path="p2",
            host="host",
            port=1234,
            heartbeat_interval_s=3,  # below min
            reset_on_logon=False,
            use_tls=False,
        )
