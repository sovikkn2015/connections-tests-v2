"""
Tests for Gap 4: BSA/AML Monitoring.

Covers: CTR threshold, aggregate CTR, structuring detection, rapid movement,
geographic risk, unusual volume, sanctions screening, anti-tipping-off,
CDD refresh dates, edge cases.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent


def _load_local(name: str):
    """Load a module from this directory by file path (avoids sys.path collisions)."""
    spec = importlib.util.spec_from_file_location(
        f"bsa_{name}", _HERE / f"{name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_models = _load_local("models")
sys.modules["models"] = _models
_monitor = _load_local("monitor")

BSAAMLMonitor = _monitor.BSAAMLMonitor
Transaction = _models.Transaction
TransactionType = _models.TransactionType
AlertType = _models.AlertType
AlertSeverity = _models.AlertSeverity
SanctionsListSource = _models.SanctionsListSource
FilingStatus = _models.FilingStatus

NOW = datetime.now(timezone.utc)


def _txn(
    client_id: str = "C-100",
    amount: float = 5000.0,
    txn_type: TransactionType = TransactionType.CASH,
    days_ago: int = 0,
    destination_country: str | None = None,
) -> Transaction:
    """Helper to create test transactions."""
    return Transaction(
        client_id=client_id,
        amount=amount,
        type=txn_type,
        timestamp=NOW - timedelta(days=days_ago),
        destination_country=destination_country,
    )


# ── CTR threshold ────────────────────────────────────────────────


class TestCTRThreshold:
    def test_cash_above_10k_triggers_ctr(self):
        mon = BSAAMLMonitor()
        txn = _txn(amount=15_000.0)
        result = mon.check_ctr_threshold(txn)
        assert result is not None
        assert result.amount == 15_000.0
        assert result.filing_status == FilingStatus.PENDING

    def test_cash_exactly_10k_no_ctr(self):
        mon = BSAAMLMonitor()
        txn = _txn(amount=10_000.0)
        result = mon.check_ctr_threshold(txn)
        assert result is None

    def test_cash_below_10k_no_ctr(self):
        mon = BSAAMLMonitor()
        txn = _txn(amount=9_999.99)
        result = mon.check_ctr_threshold(txn)
        assert result is None

    def test_wire_above_10k_no_ctr(self):
        """CTR only applies to cash transactions."""
        mon = BSAAMLMonitor()
        txn = _txn(amount=50_000.0, txn_type=TransactionType.WIRE_IN)
        result = mon.check_ctr_threshold(txn)
        assert result is None


# ── Aggregate CTR ────────────────────────────────────────────────


class TestAggregateCTR:
    def test_same_day_cash_above_10k(self):
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=6_000.0, days_ago=0),
            _txn(amount=5_000.0, days_ago=0),
        ]
        result = mon.check_aggregate_ctr("C-100", txns)
        assert result is not None
        assert result.aggregate_amount == 11_000.0
        assert result.transaction_count == 2

    def test_same_day_cash_below_10k(self):
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=4_000.0, days_ago=0),
            _txn(amount=5_000.0, days_ago=0),
        ]
        result = mon.check_aggregate_ctr("C-100", txns)
        assert result is None

    def test_different_days_no_aggregate(self):
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=6_000.0, days_ago=0),
            _txn(amount=6_000.0, days_ago=1),
        ]
        result = mon.check_aggregate_ctr("C-100", txns)
        assert result is None

    def test_empty_transactions(self):
        mon = BSAAMLMonitor()
        result = mon.check_aggregate_ctr("C-100", [])
        assert result is None


# ── Structuring detection ────────────────────────────────────────


class TestStructuring:
    def test_structuring_detected(self):
        """3+ cash txns $8K-$10K in 5 days totaling >$25K."""
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=9_500.0, days_ago=0),
            _txn(amount=9_000.0, days_ago=1),
            _txn(amount=9_200.0, days_ago=2),
        ]
        result = mon.detect_structuring("C-100", txns)
        assert result is not None
        assert result.alert_type == AlertType.STRUCTURING
        assert result.severity == AlertSeverity.HIGH
        assert result.route_to == "compliance_officer"
        assert "advisor" in result.do_not_notify
        assert "client" in result.do_not_notify

    def test_no_structuring_below_count(self):
        """Only 2 transactions — below threshold."""
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=9_500.0, days_ago=0),
            _txn(amount=9_000.0, days_ago=1),
        ]
        result = mon.detect_structuring("C-100", txns)
        assert result is None

    def test_no_structuring_below_amount_range(self):
        """Transactions below $8K — not in structuring range."""
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=7_000.0, days_ago=0),
            _txn(amount=7_500.0, days_ago=1),
            _txn(amount=7_200.0, days_ago=2),
        ]
        result = mon.detect_structuring("C-100", txns)
        assert result is None

    def test_no_structuring_below_total(self):
        """3 txns in range but total <$25K."""
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=8_000.0, days_ago=0),
            _txn(amount=8_000.0, days_ago=1),
            _txn(amount=8_000.0, days_ago=2),
        ]
        result = mon.detect_structuring("C-100", txns)
        assert result is None

    def test_empty_transactions(self):
        mon = BSAAMLMonitor()
        result = mon.detect_structuring("C-100", [])
        assert result is None


# ── Rapid movement ───────────────────────────────────────────────


class TestRapidMovement:
    def test_rapid_movement_detected(self):
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=60_000.0, txn_type=TransactionType.WIRE_IN, days_ago=0),
            _txn(amount=50_000.0, txn_type=TransactionType.WIRE_OUT, days_ago=1),
        ]
        result = mon.detect_rapid_movement("C-100", txns)
        assert result is not None
        assert result.alert_type == AlertType.RAPID_MOVEMENT
        assert result.severity == AlertSeverity.HIGH

    def test_no_rapid_movement_low_inflow(self):
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=40_000.0, txn_type=TransactionType.WIRE_IN, days_ago=0),
            _txn(amount=35_000.0, txn_type=TransactionType.WIRE_OUT, days_ago=1),
        ]
        result = mon.detect_rapid_movement("C-100", txns)
        assert result is None

    def test_no_rapid_movement_low_outflow_ratio(self):
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=60_000.0, txn_type=TransactionType.WIRE_IN, days_ago=0),
            _txn(amount=20_000.0, txn_type=TransactionType.WIRE_OUT, days_ago=1),
        ]
        result = mon.detect_rapid_movement("C-100", txns)
        assert result is None


# ── Geographic risk ──────────────────────────────────────────────


class TestGeographicRisk:
    def test_high_risk_country_detected(self):
        mon = BSAAMLMonitor()
        txn = _txn(
            amount=10_000.0,
            txn_type=TransactionType.WIRE_OUT,
            destination_country="IR",
        )
        result = mon.detect_geographic_risk(txn)
        assert result is not None
        assert result.alert_type == AlertType.GEOGRAPHIC_RISK
        assert result.severity == AlertSeverity.MEDIUM

    def test_safe_country_no_alert(self):
        mon = BSAAMLMonitor()
        txn = _txn(
            amount=10_000.0,
            txn_type=TransactionType.WIRE_OUT,
            destination_country="GB",
        )
        result = mon.detect_geographic_risk(txn)
        assert result is None

    def test_high_risk_below_threshold(self):
        mon = BSAAMLMonitor()
        txn = _txn(
            amount=4_000.0,
            txn_type=TransactionType.WIRE_OUT,
            destination_country="IR",
        )
        result = mon.detect_geographic_risk(txn)
        assert result is None

    def test_no_destination_country(self):
        mon = BSAAMLMonitor()
        txn = _txn(amount=10_000.0, txn_type=TransactionType.WIRE_OUT)
        result = mon.detect_geographic_risk(txn)
        assert result is None


# ── Unusual volume ───────────────────────────────────────────────


class TestUnusualVolume:
    def test_unusual_volume_detected(self):
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=100_000.0, txn_type=TransactionType.WIRE_IN, days_ago=0),
        ]
        result = mon.detect_unusual_volume("C-100", txns, avg_monthly=20_000.0)
        assert result is not None
        assert result.alert_type == AlertType.UNUSUAL_PATTERN

    def test_normal_volume_no_alert(self):
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=50_000.0, txn_type=TransactionType.WIRE_IN, days_ago=0),
        ]
        result = mon.detect_unusual_volume("C-100", txns, avg_monthly=20_000.0)
        assert result is None

    def test_zero_avg_no_alert(self):
        mon = BSAAMLMonitor()
        txns = [_txn(amount=1_000.0)]
        result = mon.detect_unusual_volume("C-100", txns, avg_monthly=0.0)
        assert result is None


# ── Sanctions screening ──────────────────────────────────────────


class TestSanctionsScreening:
    def test_sanctions_match(self):
        mon = BSAAMLMonitor()
        sanctions = {"EVIL CORP": SanctionsListSource.OFAC}
        result = mon.screen_sanctions("Evil Corp", sanctions)
        assert result is not None
        assert result.matched_entity == "EVIL CORP"
        assert result.list_source == SanctionsListSource.OFAC
        assert result.match_confidence == 1.0

    def test_sanctions_no_match(self):
        mon = BSAAMLMonitor()
        sanctions = {"EVIL CORP": SanctionsListSource.OFAC}
        result = mon.screen_sanctions("Good Corp", sanctions)
        assert result is None

    def test_sanctions_case_insensitive(self):
        mon = BSAAMLMonitor()
        sanctions = {"evil corp": SanctionsListSource.EU}
        result = mon.screen_sanctions("EVIL CORP", sanctions)
        assert result is not None


# ── Anti-tipping-off ─────────────────────────────────────────────


class TestAntiTippingOff:
    """
    CRITICAL: SAR alerts MUST route to compliance_officer ONLY.
    Advisor and client MUST NEVER be notified.
    Violation of 31 USC §5318(g)(2) is a federal felony.
    """

    def test_structuring_routes_to_compliance_officer(self):
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=9_500.0, days_ago=0),
            _txn(amount=9_000.0, days_ago=1),
            _txn(amount=9_200.0, days_ago=2),
        ]
        alert = mon.detect_structuring("C-100", txns)
        assert alert is not None
        assert alert.route_to == "compliance_officer"
        assert "advisor" in alert.do_not_notify
        assert "client" in alert.do_not_notify

    def test_rapid_movement_routes_to_compliance_officer(self):
        mon = BSAAMLMonitor()
        txns = [
            _txn(amount=60_000.0, txn_type=TransactionType.WIRE_IN, days_ago=0),
            _txn(amount=50_000.0, txn_type=TransactionType.WIRE_OUT, days_ago=1),
        ]
        alert = mon.detect_rapid_movement("C-100", txns)
        assert alert is not None
        assert alert.route_to == "compliance_officer"
        assert "advisor" in alert.do_not_notify
        assert "client" in alert.do_not_notify

    def test_geographic_risk_routes_to_compliance_officer(self):
        mon = BSAAMLMonitor()
        txn = _txn(amount=10_000.0, txn_type=TransactionType.WIRE_OUT, destination_country="KP")
        alert = mon.detect_geographic_risk(txn)
        assert alert is not None
        assert alert.route_to == "compliance_officer"
        assert "advisor" in alert.do_not_notify
        assert "client" in alert.do_not_notify

    def test_unusual_volume_routes_to_compliance_officer(self):
        mon = BSAAMLMonitor()
        txns = [_txn(amount=100_000.0)]
        alert = mon.detect_unusual_volume("C-100", txns, avg_monthly=20_000.0)
        assert alert is not None
        assert alert.route_to == "compliance_officer"
        assert "advisor" in alert.do_not_notify
        assert "client" in alert.do_not_notify


# ── CDD refresh dates ───────────────────────────────────────────


class TestCDDRefresh:
    def test_high_risk_12_months(self):
        mon = BSAAMLMonitor()
        last = date(2026, 1, 1)
        next_date = mon.get_cdd_refresh_date("high", last)
        expected = last + timedelta(days=12 * 30)
        assert next_date == expected

    def test_medium_risk_24_months(self):
        mon = BSAAMLMonitor()
        last = date(2026, 1, 1)
        next_date = mon.get_cdd_refresh_date("medium", last)
        expected = last + timedelta(days=24 * 30)
        assert next_date == expected

    def test_low_risk_36_months(self):
        mon = BSAAMLMonitor()
        last = date(2026, 1, 1)
        next_date = mon.get_cdd_refresh_date("low", last)
        expected = last + timedelta(days=36 * 30)
        assert next_date == expected
