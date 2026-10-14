"""Unit tests for ``m13_fix_bridge.drop_copy`` — Spec §R6."""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone

import pytest

from m13_fix_bridge.audit import StdoutAuditEmitter
from m13_fix_bridge.drop_copy import (
    DropCopyEmitter,
    TraderAidCorrelation,
    hash_account,
)


_TEST_SALT = b"m13-test-salt-32-bytes-exactly!!"


def _captured_emitter() -> tuple[StdoutAuditEmitter, io.StringIO]:
    buf = io.StringIO()
    em = StdoutAuditEmitter(stream=buf)
    return em, buf


def _read_json_lines(buf: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line]


def test_hash_account_deterministic() -> None:
    h1 = hash_account("ACCT_001", _TEST_SALT)
    h2 = hash_account("ACCT_001", _TEST_SALT)
    assert h1 == h2
    assert len(h1) == 16
    assert all(c in "0123456789abcdef" for c in h1)


def test_hash_account_salt_changes_output() -> None:
    h1 = hash_account("ACCT_001", b"salt_1_32_bytes_xxxxxxxxxxxxxxxx")
    h2 = hash_account("ACCT_001", b"salt_2_32_bytes_xxxxxxxxxxxxxxxx")
    assert h1 != h2


def test_hash_account_short_salt_rejected() -> None:
    with pytest.raises(ValueError):
        hash_account("ACCT", b"short")


def test_hash_account_empty_rejected() -> None:
    with pytest.raises(ValueError):
        hash_account("", _TEST_SALT)


def test_trader_aid_correlator_lookup_after_remember() -> None:
    c = TraderAidCorrelation()
    c.remember("CL-001", "aid-trader-1")
    assert c.lookup("CL-001") == "aid-trader-1"


def test_trader_aid_correlator_lru_evicts() -> None:
    c = TraderAidCorrelation(max_size=3)
    c.remember("A", "aid-A")
    c.remember("B", "aid-B")
    c.remember("C", "aid-C")
    c.remember("D", "aid-D")  # evicts A
    assert c.lookup("A") is None
    assert c.lookup("B") == "aid-B"
    assert c.lookup("D") == "aid-D"


def test_emit_exec_report_shape_no_raw_account() -> None:
    em, buf = _captured_emitter()
    corr = TraderAidCorrelation()
    corr.remember("CL-001", "aid-trader-1")
    dc = DropCopyEmitter(audit=em, account_salt=_TEST_SALT, correlator=corr)
    dc.on_exec_report(
        venue="brokerx",
        report={
            "cl_ord_id": "CL-001",
            "order_id": "OID-42",
            "exec_type": "2",
            "ord_status": "2",
            "last_qty": "100",
            "last_px": "183.52",
            "cum_qty": "100",
            "avg_px": "183.52",
            "transact_time": datetime.now(tz=timezone.utc),
            "account": "ACCT_REAL_123",
        },
        tenant_id="tenant-001",
    )
    lines = _read_json_lines(buf)
    exec_line = [l for l in lines if l["kind"] == "fix.exec_report"][0]
    # Raw account absent.
    assert "account" not in exec_line
    # Hashed account present.
    assert "account_hash" in exec_line
    assert exec_line["account_hash"] == hash_account("ACCT_REAL_123", _TEST_SALT)
    # Trader AID correlated.
    assert exec_line["trader_aid"] == "aid-trader-1"
    # Tenant ID pass-through.
    assert exec_line["tenant_id"] == "tenant-001"


def test_emit_exec_report_orphan_when_uncorrelated() -> None:
    em, buf = _captured_emitter()
    dc = DropCopyEmitter(audit=em, account_salt=_TEST_SALT)
    dc.on_exec_report(
        venue="brokerx",
        report={
            "cl_ord_id": "CL-OTHER",
            "order_id": "OID-99",
            "exec_type": "0",
            "ord_status": "0",
            "cum_qty": "0",
            "transact_time": datetime.now(tz=timezone.utc),
            "account": "ACCT_X",
        },
        tenant_id="tenant-001",
    )
    lines = _read_json_lines(buf)
    kinds = [l["kind"] for l in lines]
    assert "fix.drop_copy_orphan" in kinds
    assert "fix.exec_report" in kinds
    exec_line = [l for l in lines if l["kind"] == "fix.exec_report"][0]
    assert exec_line["trader_aid"] is None


def test_emit_cancel_reject_shape() -> None:
    em, buf = _captured_emitter()
    corr = TraderAidCorrelation()
    corr.remember("CL-005", "aid-X")
    dc = DropCopyEmitter(audit=em, account_salt=_TEST_SALT, correlator=corr)
    dc.on_cancel_reject(
        venue="brokerx",
        reject={
            "cl_ord_id": "CL-005",
            "order_id": "OID-5",
            "cxl_rej_reason": "1",
            "cxl_rej_response_to": "1",
            "account": "ACCT_Y",
        },
        tenant_id="tenant-A",
    )
    lines = _read_json_lines(buf)
    rej = [l for l in lines if l["kind"] == "fix.cancel_reject"][0]
    assert rej["cxl_rej_reason"] == "1"
    assert rej["account_hash"] == hash_account("ACCT_Y", _TEST_SALT)
    assert rej["trader_aid"] == "aid-X"


def test_disabled_drop_copy_emits_nothing() -> None:
    em, buf = _captured_emitter()
    dc = DropCopyEmitter(
        audit=em,
        account_salt=_TEST_SALT,
        enabled=False,
    )
    dc.on_exec_report(
        venue="brokerx",
        report={"cl_ord_id": "CL", "order_id": "O", "account": "ACCT"},
        tenant_id="t",
    )
    assert buf.getvalue() == ""


def test_set_enabled_toggles_behavior() -> None:
    em, buf = _captured_emitter()
    dc = DropCopyEmitter(audit=em, account_salt=_TEST_SALT, enabled=False)
    dc.set_enabled(True)
    dc.on_exec_report(
        venue="brokerx",
        report={
            "cl_ord_id": "CL-1",
            "order_id": "OID-1",
            "exec_type": "0",
            "ord_status": "0",
            "cum_qty": "0",
            "transact_time": datetime.now(tz=timezone.utc),
            "account": "ACCT_Z",
        },
        tenant_id="t",
    )
    lines = _read_json_lines(buf)
    assert any(l["kind"] == "fix.exec_report" for l in lines)


def test_drop_copy_salt_validates_min_length() -> None:
    em, _ = _captured_emitter()
    with pytest.raises(ValueError):
        DropCopyEmitter(audit=em, account_salt=b"short")
