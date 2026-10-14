"""
Gap 4 — Unit tests.

Covers T4.1..T4.38 (T4.39-T4.41 live in tests/integration/). Maps 1:1
to acceptance criteria in .kiro/specs/gap4-bsa-aml-monitoring.md §4.
"""

from __future__ import annotations

import ast
import threading
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from m2_m4_policy_engine import (
    AuthorityPolicy,
    Decision,
    PolicyDecision,
    PolicyInput,
    PolicyRule,
    RULE_APPLIED_RE as M2_RULE_RE,
    WSP_SECTION_RE as M2_WSP_RE,
)
from m3_schema_registry import (
    AccountType,
    AuditEntry,
    Transaction,
    TransactionType,
)
from m5_config_loader import BsaAmlConfig
from m10_audit_logger import (
    AuditLogger,
    AuditWriteError,
    InMemoryAuditBackend,
    InMemoryAuditDLQ,
)

from compliance.gap4_bsa_aml_monitoring import (
    ALERT_REASONS,
    AlertEmitFailed,
    AlertSeverity,
    AlertType,
    AuditEmitter,
    BsaAmlAlert,
    BsaAmlEngine,
    CashTransaction,
    CashTransactionCategory,
    CtrMonitor,
    CtrPolicyRule,
    InMemoryWindowStore,
    NotACashTransactionError,
    RedisWindowStore,
    SarStructuringMonitor,
    SarStructuringPolicyRule,
    WindowStore,
)


# =============================================================================
# Fixtures
# =============================================================================


_FIRM = "firm-test-1"
_CLIENT = UUID("00000000-0000-0000-0000-000000000001")
_ACCOUNT = UUID("00000000-0000-0000-0000-000000000002")
_BASE_TS = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)


def _cash_txn(
    *,
    amount: str | int | float | Decimal,
    category: CashTransactionCategory = CashTransactionCategory.cash_deposit,
    delta_seconds: int = 0,
    firm_id: str = _FIRM,
    client_id: UUID = _CLIENT,
    account_id: UUID = _ACCOUNT,
    trace_id: str = "trace-test-1",
) -> CashTransaction:
    return CashTransaction(
        txn_id=uuid4(),
        client_id=client_id,
        account_id=account_id,
        category=category,
        amount_usd=Decimal(str(amount)),
        occurred_at=_BASE_TS + timedelta(seconds=delta_seconds),
        firm_id=firm_id,
        source_txn_ref="src-1",
        trace_id=trace_id,
    )


def _make_config(
    *,
    enabled: bool = True,
    ctr: float = 10000.0,
    sar: float = 7000.0,
) -> BsaAmlConfig:
    return BsaAmlConfig(
        enabled=enabled,
        ctr_threshold=ctr,
        sar_structuring_threshold=sar,
    )


class _FixedClock:
    """Callable[[], datetime] returning a fixed UTC timestamp."""

    def __init__(self, ts: datetime) -> None:
        self._ts = ts

    def __call__(self) -> datetime:
        return self._ts


@pytest.fixture
def clock() -> _FixedClock:
    return _FixedClock(_BASE_TS + timedelta(hours=1))


@pytest.fixture
def store() -> InMemoryWindowStore:
    return InMemoryWindowStore()


@pytest.fixture
def cfg() -> BsaAmlConfig:
    return _make_config()


@pytest.fixture
def cfg_disabled() -> BsaAmlConfig:
    return _make_config(enabled=False)


@pytest.fixture
def engine(cfg, store, clock) -> BsaAmlEngine:
    return BsaAmlEngine(config=cfg, store=store, clock=clock)


# =============================================================================
# T4.1 — Enums
# =============================================================================


def test_t4_1_cash_transaction_category_values():
    assert {c.value for c in CashTransactionCategory} == {
        "cash_deposit",
        "cash_withdrawal",
        "wire_in",
        "wire_out",
    }


def test_t4_1_alert_severity_values():
    assert {s.value for s in AlertSeverity} == {
        "low",
        "medium",
        "high",
        "critical",
    }


def test_t4_1_alert_type_values():
    assert {t.value for t in AlertType} == {
        "ctr_threshold",
        "ctr_aggregate",
        "sar_structuring",
    }


# =============================================================================
# T4.2 — CashTransaction frozen, Decimal, validation
# =============================================================================


def test_t4_2_cash_txn_happy_path():
    t = _cash_txn(amount="10000.00")
    assert t.amount_usd == Decimal("10000.00")
    assert isinstance(t.amount_usd, Decimal)
    with pytest.raises(ValidationError):
        t.amount_usd = Decimal("1")  # type: ignore[misc]


def test_t4_2_cash_txn_naive_datetime_rejected():
    with pytest.raises(ValidationError):
        CashTransaction(
            txn_id=uuid4(),
            client_id=_CLIENT,
            account_id=_ACCOUNT,
            category=CashTransactionCategory.cash_deposit,
            amount_usd=Decimal("100"),
            occurred_at=datetime(2026, 4, 14, 12, 0, 0),  # naive
            firm_id=_FIRM,
            source_txn_ref="s",
            trace_id="t",
        )


def test_t4_2_cash_txn_negative_amount_rejected():
    with pytest.raises(ValidationError):
        _cash_txn(amount="-100")


def test_t4_2_cash_txn_zero_amount_rejected():
    with pytest.raises(ValidationError):
        _cash_txn(amount="0")


# =============================================================================
# T4.3 / T4.4 — from_m3 adapter
# =============================================================================


def _m3_wire_in(amount: float = 50000.0) -> Transaction:
    return Transaction(
        transaction_id=uuid4(),
        account_ref=_ACCOUNT,
        client_ref=_CLIENT,
        transaction_type=TransactionType.WIRE_IN,
        amount=amount,
        trade_date=date(2026, 4, 14),
        source_system="test_custodian",
        source_id="src-wire-1",
        source_transaction_type="incoming_wire",
        trace_id="trace-wire-1",
        created_at=_BASE_TS,
    )


def test_t4_3_from_m3_wire_in():
    ct = CashTransaction.from_m3(_m3_wire_in(50000.0))
    assert ct.category == CashTransactionCategory.wire_in
    assert ct.amount_usd == Decimal("50000.0")


def test_t4_3_from_m3_wire_out():
    m = _m3_wire_in()
    m2 = m.model_copy(update={"transaction_type": TransactionType.WIRE_OUT})
    ct = CashTransaction.from_m3(m2)
    assert ct.category == CashTransactionCategory.wire_out


def test_t4_3_from_m3_contribution_with_cash_deposit_hint():
    m = Transaction(
        transaction_id=uuid4(),
        account_ref=_ACCOUNT,
        client_ref=_CLIENT,
        transaction_type=TransactionType.CONTRIBUTION,
        amount=5000.0,
        trade_date=date(2026, 4, 14),
        source_system="test_custodian",
        source_id="src-1",
        source_transaction_type="cash_deposit",
        trace_id="trace-1",
        created_at=_BASE_TS,
    )
    ct = CashTransaction.from_m3(m)
    assert ct.category == CashTransactionCategory.cash_deposit


def test_t4_3_from_m3_distribution_with_cash_withdrawal_hint():
    m = Transaction(
        transaction_id=uuid4(),
        account_ref=_ACCOUNT,
        client_ref=_CLIENT,
        transaction_type=TransactionType.DISTRIBUTION,
        amount=5000.0,
        trade_date=date(2026, 4, 14),
        source_system="test_custodian",
        source_id="src-1",
        source_transaction_type="cash_withdrawal",
        trace_id="trace-1",
        created_at=_BASE_TS,
    )
    ct = CashTransaction.from_m3(m)
    assert ct.category == CashTransactionCategory.cash_withdrawal


@pytest.mark.parametrize(
    "ttype",
    [
        TransactionType.BUY,
        TransactionType.SELL,
        TransactionType.DIVIDEND,
        TransactionType.INTEREST,
        TransactionType.FEE,
        TransactionType.REINVESTMENT,
        TransactionType.CORPORATE_ACTION,
    ],
)
def test_t4_4_from_m3_rejects_non_cash(ttype):
    m = _m3_wire_in()
    m2 = m.model_copy(update={"transaction_type": ttype})
    with pytest.raises(NotACashTransactionError):
        CashTransaction.from_m3(m2)


# =============================================================================
# T4.5 / T4.6 / T4.7 / T4.8 — BsaAmlAlert invariants
# =============================================================================


def _valid_alert_kwargs() -> dict:
    return dict(
        alert_id=uuid4(),
        rule_id="authority/bsa_aml/ctr.v1",
        alert_type=AlertType.ctr_threshold,
        severity=AlertSeverity.high,
        client_id=_CLIENT,
        firm_id=_FIRM,
        threshold_type="ctr_single",
        threshold_value_usd=Decimal("10000.00"),
        matched_transactions=(uuid4(),),
        matched_amount_usd=Decimal("12000.00"),
        wsp_section="WSP-BSA-8.2",
        rule_applied="authority/bsa_aml/ctr.v1",
        route_to="compliance_officer",
        do_not_notify=("advisor", "client"),
        detected_at=_BASE_TS,
        reason_code="ctr_threshold_exceeded",
        reason_detail="single cash deposit exceeds CTR threshold",
    )


def test_t4_5_alert_happy_path_frozen():
    a = BsaAmlAlert(**_valid_alert_kwargs())
    assert a.route_to == "compliance_officer"
    with pytest.raises(ValidationError):
        a.severity = AlertSeverity.low  # type: ignore[misc]


def test_t4_5_alert_rejects_non_compliance_route():
    kwargs = _valid_alert_kwargs()
    kwargs["route_to"] = "advisor"
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


def test_t4_5_alert_rejects_do_not_notify_without_advisor():
    kwargs = _valid_alert_kwargs()
    kwargs["do_not_notify"] = ("client", "regulator")
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


def test_t4_5_alert_rejects_do_not_notify_without_client():
    kwargs = _valid_alert_kwargs()
    kwargs["do_not_notify"] = ("advisor", "regulator")
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


def test_t4_5_alert_rejects_bad_wsp_section():
    kwargs = _valid_alert_kwargs()
    kwargs["wsp_section"] = "not-a-wsp"
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


def test_t4_5_alert_rejects_bad_rule_applied():
    kwargs = _valid_alert_kwargs()
    kwargs["rule_applied"] = "bogus"
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


@pytest.mark.parametrize(
    "bad",
    [
        "details with ssn 123-45-6789",
        "contact reviewer@firm.com",
        "account 123456789012 flagged",
        "IBAN DE89370400440532013000",
    ],
)
def test_t4_6_alert_pii_in_reason_detail_rejected(bad):
    kwargs = _valid_alert_kwargs()
    kwargs["reason_detail"] = bad
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


def test_t4_7_alert_reason_code_must_be_in_vocab():
    assert "ctr_threshold_exceeded" in ALERT_REASONS
    assert "ctr_aggregate_exceeded" in ALERT_REASONS
    assert "structuring_pattern_detected" in ALERT_REASONS

    kwargs = _valid_alert_kwargs()
    kwargs["reason_code"] = "not_in_vocab"
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


def test_t4_8_alert_matched_transactions_must_be_unique():
    u = uuid4()
    kwargs = _valid_alert_kwargs()
    kwargs["matched_transactions"] = (u, u)
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


def test_t4_8_alert_matched_transactions_nonempty():
    kwargs = _valid_alert_kwargs()
    kwargs["matched_transactions"] = ()
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


def test_t4_5_alert_rejects_zero_matched_amount():
    kwargs = _valid_alert_kwargs()
    kwargs["matched_amount_usd"] = Decimal("0")
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


# =============================================================================
# T4.9..T4.13 — InMemoryWindowStore
# =============================================================================


def test_t4_9_window_store_protocol_implemented():
    assert isinstance(InMemoryWindowStore(), WindowStore)


def test_t4_10_record_keeps_sorted(store):
    key = (_FIRM, _CLIENT)
    # Insert in unsorted order.
    t1 = _cash_txn(amount="100", delta_seconds=30)
    t2 = _cash_txn(amount="200", delta_seconds=10)
    t3 = _cash_txn(amount="300", delta_seconds=20)
    for t in (t1, t2, t3):
        store.record(key, t)
    # Within a wide window returns them in occurred_at order.
    result = store.within(
        key,
        start=_BASE_TS - timedelta(seconds=1),
        end=_BASE_TS + timedelta(seconds=100),
    )
    assert [t.amount_usd for t in result] == [
        Decimal("200"),
        Decimal("300"),
        Decimal("100"),
    ]


def test_t4_11_within_boundary_semantics(store):
    """start exclusive, end inclusive."""
    key = (_FIRM, _CLIENT)
    t_at_start = _cash_txn(amount="100", delta_seconds=100)
    t_mid = _cash_txn(amount="200", delta_seconds=150)
    t_at_end = _cash_txn(amount="300", delta_seconds=200)
    for t in (t_at_start, t_mid, t_at_end):
        store.record(key, t)

    start = _BASE_TS + timedelta(seconds=100)  # exactly at t_at_start
    end = _BASE_TS + timedelta(seconds=200)  # exactly at t_at_end

    result = store.within(key, start=start, end=end)
    # t_at_start is at the start boundary → excluded.
    # t_at_end is at the end boundary → included.
    ids = {t.amount_usd for t in result}
    assert ids == {Decimal("200"), Decimal("300")}


def test_t4_12_within_category_filter(store):
    key = (_FIRM, _CLIENT)
    store.record(
        key,
        _cash_txn(
            amount="100",
            category=CashTransactionCategory.cash_deposit,
            delta_seconds=10,
        ),
    )
    store.record(
        key,
        _cash_txn(
            amount="200",
            category=CashTransactionCategory.wire_in,
            delta_seconds=20,
        ),
    )
    deposits = store.within(
        key,
        start=_BASE_TS,
        end=_BASE_TS + timedelta(seconds=100),
        categories=frozenset({CashTransactionCategory.cash_deposit}),
    )
    assert [t.amount_usd for t in deposits] == [Decimal("100")]


def test_t4_13_purge_before_removes_old(store):
    key = (_FIRM, _CLIENT)
    store.record(key, _cash_txn(amount="100", delta_seconds=10))
    store.record(key, _cash_txn(amount="200", delta_seconds=20))
    # Purge everything before delta_seconds=15 → remove the first one.
    removed = store.purge_before(_BASE_TS + timedelta(seconds=15))
    assert removed == 1
    assert store.size() == 1


# =============================================================================
# T4.14 — thread safety
# =============================================================================


def test_t4_14_thread_safety():
    store = InMemoryWindowStore()
    key = (_FIRM, _CLIENT)
    results: list[bool] = []
    errors: list[BaseException] = []

    def worker(i: int) -> None:
        try:
            for j in range(10):
                # amount must be > 0; shift by 1 so the (0,0) case is valid.
                store.record(
                    key,
                    _cash_txn(
                        amount=str(i * 100 + j + 1),
                        delta_seconds=i * 100 + j,
                    ),
                )
            results.append(True)
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(results) == 10
    assert store.size() == 100


def test_t4_14_has_lock():
    store = InMemoryWindowStore()
    # The lock is an internal implementation detail; expose its presence
    # via the attribute name to anchor the invariant.
    assert hasattr(store, "_lock")
    assert isinstance(store._lock, type(threading.Lock()))  # type: ignore[arg-type]


# =============================================================================
# T4.15 — RedisWindowStore stub
# =============================================================================


def test_t4_15_redis_stub_not_implemented():
    r = RedisWindowStore(redis_url="redis://localhost:6379/0")
    with pytest.raises(NotImplementedError):
        r.record((_FIRM, _CLIENT), _cash_txn(amount="100"))
    with pytest.raises(NotImplementedError):
        r.within(
            (_FIRM, _CLIENT),
            start=_BASE_TS,
            end=_BASE_TS + timedelta(hours=1),
        )
    with pytest.raises(NotImplementedError):
        r.purge_before(_BASE_TS)


def test_t4_15_redis_stub_rejects_empty_url():
    with pytest.raises(ValueError):
        RedisWindowStore(redis_url="")


# =============================================================================
# T4.16..T4.19 — CtrMonitor
# =============================================================================


def test_t4_16_ctr_single_happy_path(engine):
    alerts = engine.evaluate_post_trade(_cash_txn(amount="10001.00"))
    assert len(alerts) >= 1
    a = alerts[0]
    assert a.alert_type == AlertType.ctr_threshold
    assert a.threshold_type == "ctr_single"
    assert a.reason_code == "ctr_threshold_exceeded"
    assert a.rule_applied == "authority/bsa_aml/ctr.v1"
    assert a.wsp_section == "WSP-BSA-8.2"


def test_t4_17_ctr_aggregate_path(engine):
    # Three $4,000 deposits within 24h → aggregate fires on the 3rd.
    for i in range(3):
        alerts = engine.evaluate_post_trade(
            _cash_txn(amount="4000.00", delta_seconds=i * 3600)
        )
    # After 3rd: aggregate total is $12,000 > $10,000.
    agg = [a for a in alerts if a.alert_type == AlertType.ctr_aggregate]
    assert len(agg) == 1
    assert agg[0].threshold_type == "ctr_aggregate_24h"
    assert agg[0].matched_amount_usd == Decimal("12000.00")


def test_t4_18_ctr_single_boundary_exactly_10k(engine):
    alerts = engine.evaluate_post_trade(_cash_txn(amount="10000.00"))
    single = [a for a in alerts if a.alert_type == AlertType.ctr_threshold]
    assert len(single) == 1


def test_t4_19_ctr_aggregate_boundary_exact_10k_no_alert(store, clock):
    # Three txns summing to exactly $10,000 → NO aggregate alert.
    # (Aggregate rule is strict `>`.)
    engine = BsaAmlEngine(config=_make_config(), store=store, clock=clock)
    alerts = None
    for amt in ["3333.33", "3333.33", "3333.34"]:
        alerts = engine.evaluate_post_trade(
            _cash_txn(amount=amt, delta_seconds=len(alerts or []))
        )
    # Sum = 10_000.00 exactly; no aggregate alert.
    assert not any(a.alert_type == AlertType.ctr_aggregate for a in alerts)


def test_t4_19_ctr_aggregate_just_over_10k_alerts(store, clock):
    engine = BsaAmlEngine(config=_make_config(), store=store, clock=clock)
    for amt, delta in [("3333.34", 0), ("3333.33", 10), ("3333.34", 20)]:
        alerts = engine.evaluate_post_trade(
            _cash_txn(amount=amt, delta_seconds=delta)
        )
    # Sum = 10_000.01 → aggregate alert.
    assert any(a.alert_type == AlertType.ctr_aggregate for a in alerts)


# =============================================================================
# T4.20..T4.23 — SarStructuringMonitor
# =============================================================================


def test_t4_20_structuring_happy_path(engine):
    for i, amt in enumerate(["8000", "8500", "7500"]):
        alerts = engine.evaluate_post_trade(
            _cash_txn(amount=amt, delta_seconds=i * 3600)
        )
    sar = [a for a in alerts if a.alert_type == AlertType.sar_structuring]
    assert len(sar) == 1
    assert sar[0].severity == AlertSeverity.critical
    assert sar[0].reason_code == "structuring_pattern_detected"
    assert sar[0].wsp_section == "WSP-BSA-8.1"


def test_t4_21_structuring_below_lower_bound_no_alert(engine):
    # Three $6,999 deposits within 7 days → NOT mid-band.
    alerts_final = ()
    for i in range(3):
        alerts_final = engine.evaluate_post_trade(
            _cash_txn(amount="6999", delta_seconds=i * 3600)
        )
    assert not any(a.alert_type == AlertType.sar_structuring for a in alerts_final)


def test_t4_22_structuring_above_ctr_threshold_no_structuring(engine):
    # Three $10,001 deposits fire CTR single alerts, not structuring.
    final_alerts = ()
    for i in range(3):
        final_alerts = engine.evaluate_post_trade(
            _cash_txn(amount="10001", delta_seconds=i * 3600)
        )
    # CTR single alerts fire; no structuring.
    assert all(
        a.alert_type != AlertType.sar_structuring for a in final_alerts
    )
    # At least one CTR single alert in this batch.
    assert any(a.alert_type == AlertType.ctr_threshold for a in final_alerts)


def test_t4_23_structuring_window_boundary(store, clock):
    # Two $8,000 deposits in days 0-3, third at day 7 + 1 second.
    engine = BsaAmlEngine(config=_make_config(), store=store, clock=clock)
    engine.evaluate_post_trade(_cash_txn(amount="8000", delta_seconds=0))
    engine.evaluate_post_trade(
        _cash_txn(amount="8000", delta_seconds=3 * 24 * 3600)
    )
    # Third at t = 7 days + 1 second past the first. The first is now
    # outside the rolling 7-day window.
    alerts = engine.evaluate_post_trade(
        _cash_txn(
            amount="8000",
            delta_seconds=7 * 24 * 3600 + 1,
        )
    )
    # Second + third are within 7 days; first dropped → only 2 midband
    # → no structuring alert.
    assert not any(a.alert_type == AlertType.sar_structuring for a in alerts)


# =============================================================================
# T4.24 / T4.25 — BsaAmlEngine disable short-circuit
# =============================================================================


def test_t4_24_disabled_engine_no_side_effects(store, clock, cfg_disabled):
    # Record alert emitter that counts writes.
    recorded_writes: list[AuditEntry] = []

    class _CountingBackend:
        tier = "worm"

        def write(self, entry: AuditEntry) -> None:
            recorded_writes.append(entry)

        def query_by_trace_id(self, trace_id: str):
            return []

    # Build real AuditLogger to make the observation realistic.
    audit = AuditLogger(
        langfuse=InMemoryAuditBackend(tier="langfuse"),
        worm=InMemoryAuditBackend(tier="worm"),
        crm=InMemoryAuditBackend(tier="crm"),
        dlq=InMemoryAuditDLQ(),
    )
    emitter = AuditEmitter(audit=audit, firm_id=_FIRM)
    engine = BsaAmlEngine(
        config=cfg_disabled, store=store, clock=clock, audit_emitter=emitter
    )
    for _ in range(100):
        out = engine.evaluate_post_trade(_cash_txn(amount="50000"))
        assert out == ()
    assert store.size() == 0
    # No audit write.
    assert len(audit._langfuse.entries) == 0  # type: ignore[attr-defined]
    assert len(audit._worm.entries) == 0  # type: ignore[attr-defined]


def test_t4_25_config_none_no_side_effects(store, clock):
    engine = BsaAmlEngine(config=None, store=store, clock=clock)
    for _ in range(10):
        assert engine.evaluate_post_trade(_cash_txn(amount="50000")) == ()
    assert store.size() == 0


# =============================================================================
# T4.26..T4.30 — M2 PolicyRule adapters
# =============================================================================


def _aid_fixture_REMOVED():  # retained for backward ref; replaced by conftest fixture
    pass


def test_t4_26_policy_rule_protocol():
    assert isinstance(CtrPolicyRule(), PolicyRule)
    assert isinstance(SarStructuringPolicyRule(), PolicyRule)


def test_t4_27_ctr_policy_rule_escalate(store, clock, fixture_aid_advisor):
    engine = BsaAmlEngine(config=_make_config(), store=store, clock=clock)
    rule = CtrPolicyRule()
    txn = _cash_txn(amount="15000")
    inp = PolicyInput(
        identity=fixture_aid_advisor,
        action="order.submit",
        target={"ticker": "X"},
        context={"cash_transaction": txn, "bsa_aml_engine": engine},
    )
    decision = rule.evaluate(inp)
    assert decision is not None
    assert decision.decision == Decision.ESCALATE
    assert decision.reason == "ctr_alert_triggered"
    assert decision.rule_applied == "authority/bsa_aml/ctr.v1"
    assert decision.wsp_section == "WSP-BSA-8.2"


def test_t4_28_ctr_policy_rule_missing_context_deny(engine, fixture_aid_advisor):
    rule = CtrPolicyRule()
    inp = PolicyInput(
        identity=fixture_aid_advisor,
        action="order.submit",
        target={"ticker": "X"},
        context={},  # no cash_transaction
    )
    decision = rule.evaluate(inp)
    assert decision is not None
    assert decision.decision == Decision.DENY
    assert decision.reason == "missing_context:cash_transaction"


def test_t4_29_ctr_policy_rule_disabled_abstains(store, clock, fixture_aid_advisor):
    disabled_engine = BsaAmlEngine(
        config=_make_config(enabled=False), store=store, clock=clock
    )
    rule = CtrPolicyRule()
    inp = PolicyInput(
        identity=fixture_aid_advisor,
        action="order.submit",
        target={"ticker": "X"},
        context={
            "cash_transaction": _cash_txn(amount="15000"),
            "bsa_aml_engine": disabled_engine,
        },
    )
    assert rule.evaluate(inp) is None


def test_t4_30_sar_policy_rule_escalate(store, clock, fixture_aid_advisor):
    engine = BsaAmlEngine(config=_make_config(), store=store, clock=clock)
    # Pre-populate 2 mid-band deposits; current txn is the 3rd.
    for i in range(2):
        engine.evaluate_post_trade(
            _cash_txn(amount="8000", delta_seconds=i * 3600)
        )
    rule = SarStructuringPolicyRule()
    current = _cash_txn(amount="8200", delta_seconds=3 * 3600)
    inp = PolicyInput(
        identity=fixture_aid_advisor,
        action="order.submit",
        target={"ticker": "X"},
        context={"cash_transaction": current, "bsa_aml_engine": engine},
    )
    decision = rule.evaluate(inp)
    assert decision is not None
    assert decision.decision == Decision.ESCALATE
    assert decision.reason == "sar_structuring_alert"


def test_t4_30_sar_policy_rule_missing_context_deny(fixture_aid_advisor):
    rule = SarStructuringPolicyRule()
    inp = PolicyInput(
        identity=fixture_aid_advisor,
        action="order.submit",
        target={"ticker": "X"},
        context={},
    )
    decision = rule.evaluate(inp)
    assert decision is not None
    assert decision.decision == Decision.DENY


def test_t4_30_sar_policy_rule_disabled_abstains(store, clock, fixture_aid_advisor):
    disabled_engine = BsaAmlEngine(
        config=_make_config(enabled=False), store=store, clock=clock
    )
    rule = SarStructuringPolicyRule()
    inp = PolicyInput(
        identity=fixture_aid_advisor,
        action="order.submit",
        target={"ticker": "X"},
        context={
            "cash_transaction": _cash_txn(amount="8500"),
            "bsa_aml_engine": disabled_engine,
        },
    )
    assert rule.evaluate(inp) is None


# =============================================================================
# T4.31 / T4.32 / T4.33 — AuditEmitter
# =============================================================================


def _valid_alert(
    *,
    rule_applied: str = "authority/bsa_aml/ctr.v1",
    wsp_section: str = "WSP-BSA-8.2",
    alert_type: AlertType = AlertType.ctr_threshold,
    reason_code: str = "ctr_threshold_exceeded",
) -> BsaAmlAlert:
    kwargs = _valid_alert_kwargs()
    kwargs["rule_id"] = rule_applied
    kwargs["rule_applied"] = rule_applied
    kwargs["wsp_section"] = wsp_section
    kwargs["alert_type"] = alert_type
    kwargs["reason_code"] = reason_code
    return BsaAmlAlert(**kwargs)


def _live_audit_logger():
    return AuditLogger(
        langfuse=InMemoryAuditBackend(tier="langfuse"),
        worm=InMemoryAuditBackend(tier="worm"),
        crm=InMemoryAuditBackend(tier="crm"),
        dlq=InMemoryAuditDLQ(),
    )


def test_t4_31_audit_emitter_populates_entry_fields():
    audit = _live_audit_logger()
    emitter = AuditEmitter(audit=audit, firm_id=_FIRM)
    alert = _valid_alert()
    txn = _cash_txn(amount="15000")
    sealed = emitter.emit(
        alert=alert,
        actor_id="system:bsa_aml_engine",
        cash_txn=txn,
    )
    assert isinstance(sealed, AuditEntry)
    assert sealed.trace_id == txn.trace_id
    assert sealed.action == "bsa_aml.alert_emitted"
    assert sealed.target_type == "cash_transaction"
    assert sealed.target_id == str(txn.txn_id)
    assert sealed.decision == "ESCALATE"
    assert sealed.reason == alert.reason_code
    assert sealed.rule_applied == alert.rule_applied
    assert sealed.wsp_section == alert.wsp_section
    assert sealed.retention_years == 6
    assert sealed.worm_record_id.startswith("bsa-aml/")
    # M10 attached the integrity hash.
    assert sealed.sha256_integrity != ""


def test_t4_32_audit_emitter_anti_tipping_off_uniform_action():
    audit = _live_audit_logger()
    emitter = AuditEmitter(audit=audit, firm_id=_FIRM)
    ctr_alert = _valid_alert()
    sar_alert = _valid_alert(
        rule_applied="authority/bsa_aml/sar_structuring.v1",
        wsp_section="WSP-BSA-8.1",
        alert_type=AlertType.sar_structuring,
        reason_code="structuring_pattern_detected",
    )
    e1 = emitter.emit(
        alert=ctr_alert, actor_id="system:x", cash_txn=_cash_txn(amount="12000")
    )
    e2 = emitter.emit(
        alert=sar_alert, actor_id="system:x", cash_txn=_cash_txn(amount="8000")
    )
    # Uniform action + target_type regardless of alert type.
    assert e1.action == e2.action == "bsa_aml.alert_emitted"
    assert e1.target_type == e2.target_type == "cash_transaction"
    # target_type MUST NOT hint at SAR filing.
    assert "sar_filing" not in (e1.target_type, e2.target_type)


def test_t4_33_audit_emitter_fail_closed_on_write_error():
    class _BrokenBackend:
        tier = "worm"

        def write(self, entry: AuditEntry) -> None:
            raise RuntimeError("simulated WORM failure")

        def query_by_trace_id(self, trace_id: str):
            return []

    audit = AuditLogger(
        langfuse=InMemoryAuditBackend(tier="langfuse"),
        worm=_BrokenBackend(),
        crm=InMemoryAuditBackend(tier="crm"),
        dlq=InMemoryAuditDLQ(),
    )
    emitter = AuditEmitter(audit=audit, firm_id=_FIRM)
    with pytest.raises(AlertEmitFailed) as exc_info:
        emitter.emit(
            alert=_valid_alert(),
            actor_id="system:x",
            cash_txn=_cash_txn(amount="12000"),
        )
    assert exc_info.value.reason == "audit_write_failed"


def test_t4_33_audit_emitter_invalid_inputs_fail_closed():
    audit = _live_audit_logger()
    emitter = AuditEmitter(audit=audit, firm_id=_FIRM)
    with pytest.raises(AlertEmitFailed) as exc_info:
        emitter.emit(
            alert="not-an-alert",  # type: ignore[arg-type]
            actor_id="system:x",
            cash_txn=_cash_txn(amount="100"),
        )
    assert exc_info.value.reason == "invalid_inputs"


def test_audit_emitter_rejects_bad_audit_logger():
    with pytest.raises(TypeError):
        AuditEmitter(audit="not-a-logger", firm_id=_FIRM)  # type: ignore[arg-type]


# =============================================================================
# T4.34 / T4.35 — Rego rules on disk + wsp_section annotations
# =============================================================================


_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGO_BUNDLE = _REPO_ROOT / "opa-bundles" / "bsa-aml"


def test_t4_34_rego_files_exist_with_wsp_annotation():
    from compliance.gap3_wsp_to_yaml import scan_rego_file

    ctr_file = _REGO_BUNDLE / "ctr.rego"
    sar_file = _REGO_BUNDLE / "sar_structuring.rego"
    assert ctr_file.is_file(), f"missing {ctr_file}"
    assert sar_file.is_file(), f"missing {sar_file}"
    ctr = scan_rego_file(ctr_file)
    sar = scan_rego_file(sar_file)
    # Every Rego file in Gap 4's bundle has at least one wsp_section.
    assert "WSP-BSA-8.2" in ctr.wsp_sections
    assert "WSP-BSA-8.1" in sar.wsp_sections


def test_t4_35_python_monitors_match_rego_wsp_sections():
    assert CtrMonitor.WSP_SECTION == "WSP-BSA-8.2"
    assert SarStructuringMonitor.WSP_SECTION == "WSP-BSA-8.1"
    assert CtrMonitor.RULE_ID == "authority/bsa_aml/ctr.v1"
    assert (
        SarStructuringMonitor.RULE_ID
        == "authority/bsa_aml/sar_structuring.v1"
    )
    # Regex coupling: Gap 4's alert regex matches M2's regex pattern.
    from compliance.gap4_bsa_aml_monitoring.models import (
        _RULE_APPLIED_RE,
        _WSP_SECTION_RE,
    )

    assert _RULE_APPLIED_RE.pattern == M2_RULE_RE.pattern
    assert _WSP_SECTION_RE.pattern == M2_WSP_RE.pattern


# =============================================================================
# T4.36 — AST import scan (module boundary)
# =============================================================================


def test_t4_36_imports_within_allowed_set():
    allowed_roots = {
        "compliance.gap4_bsa_aml_monitoring",
        "m2_m4_policy_engine",
        "m3_schema_registry",
        "m5_config_loader",
        "m10_audit_logger",
        "pydantic",
        # stdlib
        "__future__",
        "bisect",
        "collections",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "hashlib",
        "json",
        "re",
        "threading",
        "types",
        "typing",
        "uuid",
    }
    forbidden_roots = {
        "openai",
        "anthropic",
        "langchain",
        "boto3",
        "requests",
        "httpx",
        "langfuse",
    }
    import compliance.gap4_bsa_aml_monitoring as pkg

    pkg_path = Path(pkg.__file__).parent
    violations: list[tuple[str, str]] = []
    for py_file in pkg_path.rglob("*.py"):
        tree = ast.parse(py_file.read_text())
        names: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    names.append(node.module)
        for name in names:
            top = name.split(".")[0]
            if top in forbidden_roots:
                violations.append((py_file.name, name))
            elif top not in allowed_roots and not any(
                name.startswith(p) for p in allowed_roots
            ):
                violations.append((py_file.name, name))
    assert violations == [], f"forbidden imports in Gap 4: {violations}"


# =============================================================================
# T4.37 — extra='forbid' on every model
# =============================================================================


def test_t4_37_forbid_extra_cash_transaction():
    with pytest.raises(ValidationError):
        CashTransaction(
            txn_id=uuid4(),
            client_id=_CLIENT,
            account_id=_ACCOUNT,
            category=CashTransactionCategory.cash_deposit,
            amount_usd=Decimal("100"),
            occurred_at=_BASE_TS,
            firm_id=_FIRM,
            source_txn_ref="s",
            trace_id="t",
            unknown_field="x",  # type: ignore[call-arg]
        )


def test_t4_37_forbid_extra_bsa_aml_alert():
    kwargs = _valid_alert_kwargs()
    kwargs["unknown"] = "x"
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)


# =============================================================================
# T4.38 — schema_version mutation-proof
# =============================================================================


def test_t4_38_schema_version_mutation_rejected():
    kwargs = _valid_alert_kwargs()
    kwargs["schema_version"] = "2.0.0"
    with pytest.raises(ValidationError):
        BsaAmlAlert(**kwargs)
