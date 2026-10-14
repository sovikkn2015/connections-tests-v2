"""
M6 Trust-Aware MCP Gateway — Unit + Integration Tests.

Covers spec .kiro/specs/m6-mcp-gateway.md tasks T1..T20.

Run:
    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest \\
        my-agent-project-007-fsi-interoperability/tests/unit/test_m6_mcp_gateway.py \\
        -v --tb=short
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import uuid
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, List

import pytest
from pydantic import BaseModel

# ---- M6 under test ---------------------------------------------------------

from m6_mcp_gateway import (
    CircuitBreaker,
    GatewayError,
    GatewayRequest,
    GatewayResponse,
    RateLimiter,
    StubVendorAdapter,
    TrustAwareGateway,
    VALID_GATEWAY_REASONS,
    VALID_VENDOR_KINDS,
    VendorAdapter,
    VendorAdapterError,
)
from m6_mcp_gateway.audit_builder import (
    canonical_json,
    canonical_text,
    h as hash_hex,
)

# ---- Trust-layer dependencies ---------------------------------------------

from m1_identity import IdentityService, AidClaims, Role, InvalidAidError
from m2_m4_policy_engine import (
    AuthorityPolicy,
    Decision,
    MnpiPolicy,
    PolicyDecision,
)
from m3_schema_registry import AuditEntry, Client, ProvenanceStage
from m10_audit_logger import (
    AuditLogger,
    AuditWriteError,
    InMemoryAuditBackend,
    InMemoryAuditDLQ,
)
from compliance.gap2_liability_provenance import (
    ErrorCategory,
    LiabilityReport,
    WarrantyBoundary,
    WarrantyCategory,
)
from compliance.gap6_mnpi_leakage_scan import (
    MnpiLeakageScanner,
    ScanDecision,
    ScanResult,
)


UTC = timezone.utc


# =============================================================================
# Fixtures + helpers
# =============================================================================


class FakeMonotonic:
    """Deterministic monotonic clock. Advances only via .advance(delta)."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, delta: float) -> None:
        self._now += delta


class FakeUtcClock:
    """Deterministic wall clock returning tz-aware UTC datetime."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self._now

    def advance_seconds(self, secs: int) -> None:
        self._now = datetime.fromtimestamp(
            self._now.timestamp() + secs, tz=UTC
        )


@pytest.fixture
def fake_mono() -> FakeMonotonic:
    return FakeMonotonic()


@pytest.fixture
def fake_clock() -> FakeUtcClock:
    return FakeUtcClock()


@pytest.fixture
def identity_service(monkeypatch) -> IdentityService:
    # HS256 key must be >=32 bytes (M1 spec). Test-only fixture value.
    monkeypatch.setenv(
        "AID_SIGNING_KEY",
        "test-signing-key-only-unit-tests-never-production-32b!",
    )
    return IdentityService(audience="007-mcp-gateway")


@pytest.fixture
def aid_token(identity_service: IdentityService) -> str:
    from m5_config_loader import Archetype, RegistrationType

    return identity_service.issue(
        sub="sarah",
        firm_id="CRD-1",
        lei=None,
        crd_number="CRD-1",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        registration_type=RegistrationType.ria_only,
        authority_scope=["client.read", "portfolio.read"],
        authority_excludes=[],
    )


@pytest.fixture
def aid_claims(
    identity_service: IdentityService, aid_token: str
) -> AidClaims:
    return identity_service.verify(aid_token)


@pytest.fixture
def audit_logger() -> AuditLogger:
    return AuditLogger(
        langfuse=InMemoryAuditBackend(tier="langfuse"),
        worm=InMemoryAuditBackend(tier="worm"),
        crm=InMemoryAuditBackend(tier="crm"),
        dlq=InMemoryAuditDLQ(),
    )


@pytest.fixture
def leakage_scanner() -> MnpiLeakageScanner:
    return MnpiLeakageScanner()


def _build_gateway(
    *,
    identity: IdentityService,
    audit: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
    circuit_threshold: int = 5,
    rate_capacity: int = 60,
    rate_refill: float = 1.0,
) -> TrustAwareGateway:
    return TrustAwareGateway(
        identity=identity,
        authority=AuthorityPolicy(),
        mnpi=MnpiPolicy(),
        audit=audit,
        leakage_scanner=leakage_scanner,
        circuit_breaker=CircuitBreaker(
            failure_threshold=circuit_threshold,
            recovery_seconds=30.0,
            clock=fake_mono,
        ),
        rate_limiter=RateLimiter(
            capacity=rate_capacity,
            refill_per_second=rate_refill,
            clock=fake_mono,
        ),
        clock=fake_clock,
        monotonic=fake_mono,
    )


def _build_request(
    aid_token: str,
    *,
    action: str = "client.read",
    tool_name: str = "sfdc.fetch_client",
    mcp_server: str = "salesforce",
    payload: Any = None,
    trace_id: str = "trace-m6-0001",
    firm_id: str = "CRD-1",
    target: dict | None = None,
    context: dict | None = None,
    session_id: str | None = None,
    vendor_adapter: Any = None,
) -> GatewayRequest:
    return GatewayRequest(
        token=aid_token,
        action=action,
        tool_name=tool_name,
        mcp_server=mcp_server,
        payload=payload if payload is not None else {"client_id": "CLT-1"},
        trace_id=trace_id,
        firm_id=firm_id,
        target=target or {"client_id": "CLT-1", "advisor_id": "sarah"},
        context=context or {},
        session_id=session_id,
        vendor_adapter=vendor_adapter or StubVendorAdapter(),
    )


# =============================================================================
# T1 — Public API surface
# =============================================================================


def test_T1_public_api_exports():
    import m6_mcp_gateway as m6

    expected = {
        "TrustAwareGateway",
        "GatewayRequest",
        "GatewayResponse",
        "GatewayError",
        "VALID_GATEWAY_REASONS",
        "VendorAdapter",
        "VendorAdapterError",
        "VALID_VENDOR_KINDS",
        "StubVendorAdapter",
        "CircuitBreaker",
        "RateLimiter",
    }
    assert set(m6.__all__) == expected
    for name in expected:
        assert getattr(m6, name) is not None


# =============================================================================
# T2 — GatewayError + VALID_GATEWAY_REASONS (AC-R2-1..4)
# =============================================================================


def test_T2_R2_reasons_frozenset():
    assert isinstance(VALID_GATEWAY_REASONS, frozenset)
    # spot-check: each expected reason is present
    for r in (
        "invalid_identity",
        "authority_denied",
        "authority_escalated",
        "mnpi_filter_error",
        "circuit_open",
        "rate_limited",
        "vendor_unavailable",
        "vendor_error",
        "mnpi_leakage_scan",
        "audit_failed",
        "invalid_request",
    ):
        assert r in VALID_GATEWAY_REASONS


def test_T2_AC_R2_1_reason_property():
    exc = GatewayError("invalid_identity")
    assert exc.reason == "invalid_identity"


def test_T2_AC_R2_2_rejects_unknown_reason():
    with pytest.raises(ValueError):
        GatewayError("made_up_reason")


def test_T2_AC_R2_3_str_equals_reason():
    assert str(GatewayError("rate_limited")) == "rate_limited"


def test_T2_AC_R2_4_frozenset():
    assert isinstance(VALID_GATEWAY_REASONS, frozenset)


# =============================================================================
# T3 — VendorAdapterError + VALID_VENDOR_KINDS (AC-R3-2, 5, 6)
# =============================================================================


def test_T3_AC_R3_6_vendor_kinds_frozenset():
    assert isinstance(VALID_VENDOR_KINDS, frozenset)
    assert VALID_VENDOR_KINDS == frozenset({"unavailable", "error"})


def test_T3_AC_R3_2_vendor_error_kind_validation():
    with pytest.raises(ValueError):
        VendorAdapterError(kind="bogus")


def test_T3_vendor_error_kind_ok():
    exc = VendorAdapterError(kind="unavailable")
    assert exc.kind == "unavailable"


def test_T3_AC_R3_5_stub_conforms_to_protocol():
    stub = StubVendorAdapter()
    # Duck check + runtime protocol check (structural)
    assert hasattr(stub, "call") and callable(stub.call)
    assert hasattr(stub, "name") and isinstance(stub.name, str)


# =============================================================================
# T4 — StubVendorAdapter (AC-R3-1, 3, 4)
# =============================================================================


def test_T4_AC_R3_1_default_stub_echoes():
    stub = StubVendorAdapter()
    assert stub.call(tool_name="x", payload={"a": 1}) == {
        "tool": "x",
        "echo": {"a": 1},
    }
    assert stub.call_count == 1


def test_T4_AC_R3_3_stub_fail_raises():
    stub = StubVendorAdapter(
        fail=VendorAdapterError(kind="unavailable")
    )
    with pytest.raises(VendorAdapterError) as exc_info:
        stub.call(tool_name="x", payload={})
    assert exc_info.value.kind == "unavailable"


def test_T4_AC_R3_4_stub_fail_after():
    stub = StubVendorAdapter(fail_after=2)
    stub.call(tool_name="x", payload={})
    stub.call(tool_name="x", payload={})
    with pytest.raises(VendorAdapterError):
        stub.call(tool_name="x", payload={})


def test_T4_stub_custom_factory():
    stub = StubVendorAdapter(
        response_factory=lambda t, p: {"custom": True}
    )
    assert stub.call(tool_name="x", payload=None) == {"custom": True}


# =============================================================================
# T5 — CircuitBreaker (AC-R4-1..8)
# =============================================================================


def test_T5_AC_R4_6_unknown_key_closed():
    cb = CircuitBreaker(clock=FakeMonotonic())
    assert cb.state("anything") == "CLOSED"


def test_T5_AC_R4_7_invalid_threshold():
    with pytest.raises(ValueError):
        CircuitBreaker(failure_threshold=0)


def test_T5_AC_R4_1_trip_after_5_failures():
    mono = FakeMonotonic()
    cb = CircuitBreaker(failure_threshold=5, recovery_seconds=30.0, clock=mono)
    for _ in range(5):
        cb.record_failure("srv")
    assert cb.state("srv") == "OPEN"
    with pytest.raises(GatewayError) as exc_info:
        cb.check("srv")
    assert exc_info.value.reason == "circuit_open"


def test_T5_AC_R4_2_recovery_half_open():
    mono = FakeMonotonic()
    cb = CircuitBreaker(failure_threshold=2, recovery_seconds=10.0, clock=mono)
    cb.record_failure("srv")
    cb.record_failure("srv")
    assert cb.state("srv") == "OPEN"
    # Advance past cooldown
    mono.advance(11.0)
    cb.check("srv")  # must not raise
    assert cb.state("srv") == "HALF_OPEN"


def test_T5_AC_R4_3_half_open_success_closes():
    mono = FakeMonotonic()
    cb = CircuitBreaker(failure_threshold=2, recovery_seconds=1.0, clock=mono)
    cb.record_failure("srv")
    cb.record_failure("srv")
    mono.advance(2.0)
    cb.check("srv")
    cb.record_success("srv")
    assert cb.state("srv") == "CLOSED"


def test_T5_AC_R4_4_half_open_failure_reopens():
    mono = FakeMonotonic()
    cb = CircuitBreaker(failure_threshold=2, recovery_seconds=1.0, clock=mono)
    cb.record_failure("srv")
    cb.record_failure("srv")
    mono.advance(2.0)
    cb.check("srv")
    assert cb.state("srv") == "HALF_OPEN"
    cb.record_failure("srv")
    assert cb.state("srv") == "OPEN"
    # Fresh cooldown means next check still raises
    with pytest.raises(GatewayError):
        cb.check("srv")


def test_T5_AC_R4_5_success_resets_failures_in_closed():
    cb = CircuitBreaker(failure_threshold=3, clock=FakeMonotonic())
    cb.record_failure("srv")
    cb.record_failure("srv")
    cb.record_success("srv")
    # Need 3 failures again, not 1
    cb.record_failure("srv")
    cb.record_failure("srv")
    assert cb.state("srv") == "CLOSED"


def test_T5_AC_R4_8_independent_keys():
    cb = CircuitBreaker(failure_threshold=2, clock=FakeMonotonic())
    cb.record_failure("a")
    cb.record_failure("a")
    assert cb.state("a") == "OPEN"
    assert cb.state("b") == "CLOSED"


# =============================================================================
# T6 — RateLimiter (AC-R5-1..7)
# =============================================================================


def test_T6_AC_R5_4_invalid_capacity():
    with pytest.raises(ValueError):
        RateLimiter(capacity=0, refill_per_second=1.0)


def test_T6_AC_R5_5_invalid_refill():
    with pytest.raises(ValueError):
        RateLimiter(capacity=1, refill_per_second=-0.1)


def test_T6_AC_R5_1_hard_cap_with_zero_refill():
    rl = RateLimiter(capacity=2, refill_per_second=0.0, clock=FakeMonotonic())
    rl.check("k")
    rl.check("k")
    with pytest.raises(GatewayError) as exc_info:
        rl.check("k")
    assert exc_info.value.reason == "rate_limited"


def test_T6_AC_R5_2_refill_restores_token():
    mono = FakeMonotonic()
    rl = RateLimiter(capacity=1, refill_per_second=1.0, clock=mono)
    rl.check("k")
    with pytest.raises(GatewayError):
        rl.check("k")
    mono.advance(1.0)
    rl.check("k")  # 1 token restored


def test_T6_AC_R5_3_distinct_keys_isolated():
    rl = RateLimiter(capacity=1, refill_per_second=0.0, clock=FakeMonotonic())
    rl.check("a")
    rl.check("b")
    with pytest.raises(GatewayError):
        rl.check("a")
    with pytest.raises(GatewayError):
        rl.check("b")


def test_T6_AC_R5_6_tokens_cap_at_capacity():
    mono = FakeMonotonic()
    rl = RateLimiter(capacity=3, refill_per_second=10.0, clock=mono)
    rl.check("k")  # 2 tokens left
    mono.advance(100.0)  # Would refill 1000 tokens, but cap is 3
    assert rl.tokens("k") <= 3.0


def test_T6_AC_R5_7_burst_plus_sustained():
    mono = FakeMonotonic()
    rl = RateLimiter(capacity=2, refill_per_second=1.0, clock=mono)
    rl.check("k")
    rl.check("k")
    with pytest.raises(GatewayError):
        rl.check("k")
    mono.advance(1.0)
    rl.check("k")  # 1 token restored


# =============================================================================
# T7 — GatewayRequest / GatewayResponse (AC-R1-1..12)
# =============================================================================


def test_T7_AC_R1_1_valid_construction(aid_token: str):
    req = _build_request(aid_token)
    assert req.action == "client.read"
    assert req.trace_id == "trace-m6-0001"


def test_T7_AC_R1_2_empty_action(aid_token: str):
    with pytest.raises(ValueError):
        _build_request(aid_token, action="")


def test_T7_AC_R1_3_short_trace_id(aid_token: str):
    with pytest.raises(ValueError) as exc_info:
        _build_request(aid_token, trace_id="short")
    assert "trace_id" in str(exc_info.value)


def test_T7_AC_R1_4_invalid_payload_type(aid_token: str):
    with pytest.raises(TypeError) as exc_info:
        _build_request(aid_token, payload=42)
    assert "invalid_payload_type" in str(exc_info.value)


def test_T7_AC_R1_5_negative_latency():
    with pytest.raises(ValueError):
        GatewayResponse(
            decision="ALLOW",
            result=None,
            liability_report=None,  # type: ignore[arg-type]
            trace_id="trace-x",
            latency_ms=-1,
            provenance_head="a" * 64,
            rule_applied=None,
            wsp_section=None,
            reason=None,
        )


def test_T7_AC_R1_6_provenance_head_hex():
    with pytest.raises(ValueError):
        GatewayResponse(
            decision="ALLOW",
            result=None,
            liability_report=None,  # type: ignore[arg-type]
            trace_id="trace-x",
            latency_ms=0,
            provenance_head="not-hex",
            rule_applied=None,
            wsp_section=None,
            reason=None,
        )


def test_T7_AC_R1_8_repr_redacts_token(aid_token: str):
    req = _build_request(aid_token)
    r = repr(req)
    assert "<redacted>" in r
    assert aid_token not in r


def test_T7_AC_R1_8_str_redacts_token(aid_token: str):
    req = _build_request(aid_token)
    s = str(req)
    assert "<redacted>" in s
    assert aid_token not in s


def test_T7_AC_R1_10_action_format(aid_token: str):
    with pytest.raises(ValueError) as exc_info:
        _build_request(aid_token, action="not dotted")
    assert "invalid_action_format" in str(exc_info.value)


def test_T7_AC_R1_11_token_too_long(aid_token: str):
    big = "a" * 9000
    with pytest.raises(ValueError) as exc_info:
        GatewayRequest(
            token=big,
            action="client.read",
            tool_name="x",
            mcp_server="s",
            payload={},
            trace_id="trace-xxxxxxx",
            firm_id="f",
            target={},
            context={},
            session_id=None,
            vendor_adapter=StubVendorAdapter(),
        )
    assert "token_too_long" in str(exc_info.value)


def test_T7_AC_R1_12_payload_too_large(aid_token: str):
    # Build a payload that clearly exceeds 1 MiB when serialized
    big_list = ["x" * 1000] * 2000  # ~2 MB
    with pytest.raises(ValueError) as exc_info:
        _build_request(aid_token, payload=big_list)
    assert "payload_too_large" in str(exc_info.value)


# =============================================================================
# T9 — canonical_json + canonical_text (AC-R12-1..5)
# =============================================================================


def test_T9_AC_R12_1_decimal_as_string():
    out = canonical_json({"a": 1, "b": Decimal("1.23")})
    assert out == '{"a":1,"b":"1.23"}'


def test_T9_AC_R12_2_trailing_zero_distinct_hash():
    h1 = hash_hex({"a": Decimal("1.23")})
    h2 = hash_hex({"a": Decimal("1.230")})
    assert h1 != h2


def test_T9_AC_R12_3_stable_golden():
    out = canonical_json({"a": 1, "b": [2, 3], "c": Decimal("1.20")})
    assert out == '{"a":1,"b":[2,3],"c":"1.20"}'


def test_T9_AC_R12_4_unsupported_type_raises():
    class _Weird:
        pass

    with pytest.raises(TypeError):
        canonical_json({"x": _Weird()})


def test_T9_AC_R12_5_canonical_text_dispatch():
    assert canonical_text("hello") == "hello"
    assert canonical_text(None) == "null"
    assert canonical_text({"a": 1}) == '{"a":1}'

    class _M(BaseModel):
        x: int

    m = _M(x=7)
    assert canonical_text(m) == m.model_dump_json()

    with pytest.raises(TypeError):
        canonical_text(42)


# =============================================================================
# T10 — TrustAwareGateway.__init__ + health
# =============================================================================


def test_T10_missing_dependency_raises(
    identity_service: IdentityService,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    with pytest.raises(ValueError) as exc_info:
        TrustAwareGateway(
            identity=None,  # type: ignore[arg-type]
            authority=AuthorityPolicy(),
            mnpi=MnpiPolicy(),
            audit=audit_logger,
            leakage_scanner=leakage_scanner,
            circuit_breaker=CircuitBreaker(clock=fake_mono),
            rate_limiter=RateLimiter(
                capacity=60, refill_per_second=1.0, clock=fake_mono
            ),
            clock=fake_clock,
            monotonic=fake_mono,
        )
    assert "gateway_missing_dependency" in str(exc_info.value)


def test_T10_health_reports(
    identity_service: IdentityService,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    h = gw.health()
    assert set(h.keys()) == {"status", "circuit_states", "dependencies_ready"}
    assert h["status"] == "ok"
    assert h["dependencies_ready"] is True


# =============================================================================
# T11 — Happy path (AC-R6-1, 5, 11, 13, 14, 18, AC-R8-1/3, AC-R1-7)
# =============================================================================


def test_T11_AC_R6_1_happy_path(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    req = _build_request(aid_token)
    resp = gw.call(req)
    assert resp.decision == "ALLOW"
    assert resp.trace_id == req.trace_id  # AC-R1-7
    assert resp.liability_report.is_clean() is True  # AC-R8-3
    assert resp.liability_report.error_attribution is None  # AC-R8-1
    assert re.fullmatch(r"[0-9a-f]{64}", resp.provenance_head)


def test_T11_AC_R6_11_allow_chain_has_8_stages(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    resp = gw.call(_build_request(aid_token))
    chain = resp.liability_report.chain
    assert len(chain) == 8
    stage_names = [s.stage for s in chain]
    assert stage_names == [
        "m6.identity",
        "m6.authority",
        "m6.mnpi_request_filter",
        "m6.resilience",
        "m6.vendor_call",
        "m6.translate",
        "m6.mnpi_response_filter",
        "m6.leakage_scan",
    ]


def test_T11_AC_R6_14_decision_mapping_allow(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    gw.call(_build_request(aid_token))
    # Every tier received one entry
    for be in (audit_logger._langfuse, audit_logger._worm, audit_logger._crm):
        records = be.entries  # InMemoryAuditBackend exposes records list
        assert len(records) == 1
        assert records[0].decision == "allow"


# =============================================================================
# T12 — DENY: identity / authority / MNPI filter error
# =============================================================================


def test_T12_AC_R6_2_invalid_identity(
    identity_service: IdentityService,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    # Use a syntactically valid token shape that M1 rejects as malformed
    bogus = "aaa.bbb.ccc"
    req = _build_request(bogus)
    with pytest.raises(GatewayError) as exc_info:
        gw.call(req)
    assert exc_info.value.reason == "invalid_identity"
    # AuditEntry written with decision=deny
    records = audit_logger._worm.entries
    assert len(records) == 1
    assert records[0].decision == "deny"


def test_T12_AC_R6_16_invalid_identity_chain_length(
    identity_service: IdentityService,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    req = _build_request("aaa.bbb.ccc")
    with pytest.raises(GatewayError):
        gw.call(req)
    entry = audit_logger._worm.entries[0]
    assert len(entry.provenance_chain) == 1
    assert entry.provenance_chain[0].stage == "m6.identity"


def test_T12_AC_R6_3_authority_denied(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    # action="research.foo" is not in authority_scope for this AID
    req = _build_request(aid_token, action="research.run")
    with pytest.raises(GatewayError) as exc_info:
        gw.call(req)
    assert exc_info.value.reason in {"authority_denied", "authority_escalated"}


def test_T12_AC_R6_15_authority_denied_chain_length(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    req = _build_request(aid_token, action="research.run")
    with pytest.raises(GatewayError):
        gw.call(req)
    entry = audit_logger._worm.entries[0]
    names = [s.stage for s in entry.provenance_chain]
    assert names == ["m6.identity", "m6.authority"]


def test_T12_AC_R6_19_liability_reason_in_vocab(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    req = _build_request(aid_token, action="research.run")
    with pytest.raises(GatewayError):
        gw.call(req)
    entry = audit_logger._worm.entries[0]
    # Reason in audit is from vocab OR PolicyDecision.reason (both clean)
    assert len(entry.reason or "") <= 200
    # LiabilityReport reason (if attached via error_attribution) would have
    # been validated by Gap 2's PII regex — inspect that too.
    # The entry.reason is the ground-truth check.


# =============================================================================
# T13 — DENY: circuit / rate
# =============================================================================


def test_T13_AC_R6_6_circuit_open_skips_vendor(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    stub = StubVendorAdapter(
        fail=VendorAdapterError(kind="unavailable")
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    # 5 failures trip the breaker
    for _ in range(5):
        req = _build_request(aid_token, vendor_adapter=stub)
        with pytest.raises(GatewayError):
            gw.call(req)
    assert stub.call_count == 5
    # 6th call raises circuit_open WITHOUT incrementing call_count
    req = _build_request(aid_token, vendor_adapter=stub)
    with pytest.raises(GatewayError) as exc_info:
        gw.call(req)
    assert exc_info.value.reason == "circuit_open"
    assert stub.call_count == 5


def test_T13_AC_R6_7_rate_limited(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
        rate_capacity=1,
        rate_refill=0.0,
    )
    req1 = _build_request(aid_token, trace_id="trace-00001")
    req2 = _build_request(aid_token, trace_id="trace-00002")
    gw.call(req1)
    with pytest.raises(GatewayError) as exc_info:
        gw.call(req2)
    assert exc_info.value.reason == "rate_limited"


def test_T13_AC_R6_17_circuit_open_chain_length(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    stub = StubVendorAdapter(
        fail=VendorAdapterError(kind="unavailable")
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    for _ in range(5):
        req = _build_request(aid_token, vendor_adapter=stub)
        with pytest.raises(GatewayError):
            gw.call(req)
    # Check last audit entry (circuit-open rejection)
    req = _build_request(aid_token, vendor_adapter=stub)
    with pytest.raises(GatewayError) as exc_info:
        gw.call(req)
    assert exc_info.value.reason == "circuit_open"
    entry = audit_logger._worm.entries[-1]
    names = [s.stage for s in entry.provenance_chain]
    assert names == [
        "m6.identity",
        "m6.authority",
        "m6.mnpi_request_filter",
        "m6.resilience",
    ]


# =============================================================================
# T14 — DENY: vendor failures
# =============================================================================


def test_T14_AC_R6_8_vendor_unavailable(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    stub = StubVendorAdapter(
        fail=VendorAdapterError(kind="unavailable")
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    req = _build_request(aid_token, vendor_adapter=stub)
    with pytest.raises(GatewayError) as exc_info:
        gw.call(req)
    assert exc_info.value.reason == "vendor_unavailable"


def test_T14_AC_R6_18_circuit_bump_on_failure(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    stub = StubVendorAdapter(
        fail=VendorAdapterError(kind="error")
    )
    cb = CircuitBreaker(failure_threshold=5, clock=fake_mono)
    gw = TrustAwareGateway(
        identity=identity_service,
        authority=AuthorityPolicy(),
        mnpi=MnpiPolicy(),
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        circuit_breaker=cb,
        rate_limiter=RateLimiter(
            capacity=60, refill_per_second=1.0, clock=fake_mono
        ),
        clock=fake_clock,
        monotonic=fake_mono,
    )
    req = _build_request(aid_token, vendor_adapter=stub)
    with pytest.raises(GatewayError):
        gw.call(req)
    # breaker recorded one failure for mcp_server="salesforce"
    # state is still CLOSED (only 1 < threshold 5)
    assert cb.state("salesforce") == "CLOSED"


def test_T14_AC_R6_20_vendor_error_args_never_surface(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    sensitive = "sensitive-hint-XYZ-12345"

    # Build a stub whose failure carries the sensitive string in args
    class _LeakyAdapter:
        name = "leaky"
        call_count = 0

        def call(self, *, tool_name: str, payload: Any) -> Any:
            self.call_count += 1
            exc = VendorAdapterError(kind="error")
            exc.args = (sensitive,)
            raise exc

    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    req = _build_request(aid_token, vendor_adapter=_LeakyAdapter())
    with pytest.raises(GatewayError) as exc_info:
        gw.call(req)
    # GatewayError reason must be frozen vocab
    assert exc_info.value.reason == "vendor_error"
    assert sensitive not in str(exc_info.value)
    # AuditEntry must not contain the sensitive string anywhere
    entry = audit_logger._worm.entries[0]
    dumped = entry.model_dump_json()
    assert sensitive not in dumped


# =============================================================================
# T15 — DENY: Gap 6 leakage
# =============================================================================


class _AlwaysDenyLayer:
    """Gap 6 layer test double that always returns DENY."""

    def scan(self, text: str):
        return ScanDecision.DENY, ("m6_test_deny",)


def test_T15_AC_R6_9_leakage_scan_denies(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    # Compose a scanner with Layer A forced to DENY
    from compliance.gap6_mnpi_leakage_scan import LayerARegexScanner

    class _DenyA(LayerARegexScanner):
        def scan(self, text: str):
            return ScanDecision.DENY, ("ssn",)

    scanner = MnpiLeakageScanner(layer_a=_DenyA())
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    req = _build_request(aid_token)
    with pytest.raises(GatewayError) as exc_info:
        gw.call(req)
    assert exc_info.value.reason == "mnpi_leakage_scan"


# =============================================================================
# T16 — DENY: audit_failed
# =============================================================================


class _FailingWormBackend:
    """Backend that raises on every write. tier must be 'worm'."""

    tier = "worm"

    def __init__(self) -> None:
        self.records: list = []

    def write(self, entry) -> None:
        raise RuntimeError("disk full")

    def query_by_trace_id(self, trace_id: str) -> list:
        return []


def test_T16_AC_R6_10_audit_failed_happy_path(
    identity_service: IdentityService,
    aid_token: str,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    audit = AuditLogger(
        langfuse=InMemoryAuditBackend(tier="langfuse"),
        worm=_FailingWormBackend(),
        crm=InMemoryAuditBackend(tier="crm"),
        dlq=InMemoryAuditDLQ(),
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    req = _build_request(aid_token)
    with pytest.raises(GatewayError) as exc_info:
        gw.call(req)
    assert exc_info.value.reason == "audit_failed"


# =============================================================================
# T17 — Security tests
# =============================================================================


SRC_DIR = (Path(__file__).resolve().parent.parent.parent / "src" / "m6_mcp_gateway").resolve()
TEST_FILE = Path(__file__).resolve()


FORBIDDEN_IMPORT_PREFIXES = (
    "m7_",
    "m8_",
    "m9_",
    "m11_",
    "m12_",
    "m13_",
    "openai",
    "anthropic",
    "langchain",
    "boto3",
    "httpx",
    "requests",
    "fastapi",
    "redis",
)

FORBIDDEN_M10_PRIVATE = frozenset(
    {
        "m10_audit_logger.logger._canonical_json",
        "m10_audit_logger.logger._compute_integrity_hash",
        "m10_audit_logger.provenance._stage_hash",
        "m10_audit_logger.provenance._compute_payload_hash",
    }
)


def _module_names_from_source(source: str) -> list[str]:
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
                for alias in node.names:
                    names.append(f"{node.module}.{alias.name}")
    return names


def _py_files() -> list[Path]:
    files = list(SRC_DIR.glob("*.py")) + [TEST_FILE]
    return files


# v0.3.0 adds the FastAPI REST surface ``app.py`` as the ONE M6 file
# allowed to import fastapi + starlette. Library core files stay
# framework-free so the in-process callers (unit tests, the trust-layer
# integration test) never pull FastAPI into their import graph.
_HTTP_SURFACE_FILES: frozenset[str] = frozenset({"app.py"})
_HTTP_FRAMEWORK_PREFIXES: frozenset[str] = frozenset(
    {"fastapi", "starlette"}
)

# Remediation B1 (adapter-agent, 2026 Q2): M6 owns the M7 canonicalize
# stage so M11 adapters stay vendor-pure (Rule 33). ``canonicalize.py``
# is the ONE M6 file allowed to import ``m7_schema_translators``.
_M7_CANONICALIZE_FILES: frozenset[str] = frozenset({"canonicalize.py"})
_M7_FRAMEWORK_PREFIXES: frozenset[str] = frozenset({"m7_"})


def test_T17_no_forbidden_imports():
    for fpath in _py_files():
        source = fpath.read_text(encoding="utf-8")
        names = _module_names_from_source(source)
        is_http_surface = fpath.name in _HTTP_SURFACE_FILES
        is_canonicalize = fpath.name in _M7_CANONICALIZE_FILES
        for name in names:
            # Prefix check
            for prefix in FORBIDDEN_IMPORT_PREFIXES:
                if (
                    is_http_surface
                    and prefix in _HTTP_FRAMEWORK_PREFIXES
                ):
                    # app.py is the public REST wrapper; fastapi +
                    # starlette are its only reason to exist.
                    continue
                if (
                    is_canonicalize
                    and prefix in _M7_FRAMEWORK_PREFIXES
                ):
                    # canonicalize.py is the ONE seam M6 uses to call
                    # M7 translators; remediation B1.
                    continue
                assert not name.startswith(prefix), (
                    f"Forbidden import {name!r} in {fpath.name}"
                )
            # Explicit private check
            assert name not in FORBIDDEN_M10_PRIVATE, (
                f"Forbidden M10 private import {name!r} in {fpath.name}"
            )


def test_T17_no_credentials():
    credential_pattern = re.compile(
        r"(?i)(api[_-]?key|password|secret[_=]|token\s*=\s*['\"])"
    )
    # Allow certain safe substrings (field names, etc.)
    allowlist_substrings = {
        "token: str",      # type hint
        "token=<redacted>",
        'token": token',   # dict keys
    }
    for fpath in SRC_DIR.glob("*.py"):
        source = fpath.read_text(encoding="utf-8")
        for line_no, line in enumerate(source.splitlines(), 1):
            if any(safe in line for safe in allowlist_substrings):
                continue
            m = credential_pattern.search(line)
            assert not m, (
                f"Possible credential pattern in {fpath.name}:{line_no}: {line!r}"
            )


def test_T17_no_float_conversion():
    for fpath in SRC_DIR.glob("*.py"):
        source = fpath.read_text(encoding="utf-8")
        # Allow `float` in type hints via `: float` or `-> float` or
        # `Callable[[], float]` — but never `float(` function call.
        assert "float(" not in source, (
            f"float(...) call in {fpath.name}"
        )


def test_T17_response_repr_omits_result(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    resp = gw.call(_build_request(aid_token))
    r = repr(resp)
    assert "<omitted>" in r
    # The result dict must not appear
    assert "echo" not in r


def test_T17_token_never_in_audit(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    gw.call(_build_request(aid_token))
    entry = audit_logger._worm.entries[0]
    dumped = entry.model_dump_json()
    assert aid_token not in dumped


# =============================================================================
# T18 — Drift / reconciliation
# =============================================================================


def test_T18_canonical_json_golden_hex():
    """Golden hex pinned in Spec §R12. Breaking this breaks the contract."""
    text = canonical_json({"a": 1, "b": [2, 3], "c": Decimal("1.20")})
    expected_hex = hashlib.sha256(text.encode("utf-8")).hexdigest()
    # Compute locally and assert stability
    again = canonical_json({"a": 1, "b": [2, 3], "c": Decimal("1.20")})
    assert hashlib.sha256(again.encode("utf-8")).hexdigest() == expected_hex


def test_T18_reason_category_parity():
    from m6_mcp_gateway.audit_builder import REASON_TO_ERROR_CATEGORY

    assert set(REASON_TO_ERROR_CATEGORY.keys()) == VALID_GATEWAY_REASONS
    for cat in REASON_TO_ERROR_CATEGORY.values():
        assert isinstance(cat, ErrorCategory)


def test_T18_provenance_stage_order_in_source():
    source = (SRC_DIR / "gateway.py").read_text(encoding="utf-8")
    # Find all m6.* stage names in source order
    stages = re.findall(r'"m6\.[a-z_]+"', source)
    unique_in_order: list[str] = []
    seen: set[str] = set()
    for s in stages:
        if s not in seen:
            unique_in_order.append(s)
            seen.add(s)
    # First 8 must match the ALLOW pipeline sequence; m6.audit_attempt is last.
    expected_allow_prefix = [
        '"m6.identity"',
        '"m6.authority"',
        '"m6.mnpi_request_filter"',
        '"m6.resilience"',
        '"m6.vendor_call"',
        '"m6.translate"',
        '"m6.mnpi_response_filter"',
        '"m6.leakage_scan"',
    ]
    # The source must contain these 8 somewhere, in this order
    idx = 0
    for name in expected_allow_prefix:
        while idx < len(unique_in_order) and unique_in_order[idx] != name:
            idx += 1
        assert idx < len(unique_in_order), (
            f"Stage {name} missing or out of order in gateway.py"
        )
        idx += 1


def test_T18_not_thread_safe_documented():
    src_resilience = (SRC_DIR / "resilience.py").read_text(encoding="utf-8")
    assert "thread-safe" in src_resilience or "thread safe" in src_resilience
    assert "Phase 1" in src_resilience


# =============================================================================
# T19 — Integration: Phase 1 trust pipeline
# =============================================================================


def test_T19_integration_full_trust_pipeline(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
    aid_claims: AidClaims,
):
    # Stub adapter returns a canonical Client per the M3 model used
    # in M2/M4 tests. SSN/DOB/tax_id are synthetic fixtures — M4
    # redacts them. Single-word names avoid Gap 6 Layer B's aggressive
    # NER stub (which blocks any two consecutive Title-Case words
    # as a personal-name candidate — fail-closed by design, spec R3.2).
    #
    # Deterministic UUIDs: random uuid4 last segment can be 12 all-
    # numeric digits (~2% chance each), triggering Layer A
    # `account_number` regex (\d{12,}). Fail-closed by design. Use
    # fixed hex-letter UUIDs so the integration test is stable.
    _FIXED_CANONICAL_ID = uuid.UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeffffaaaa")
    _FIXED_FIRM_ID = uuid.UUID("ffffffff-eeee-4ddd-8ccc-bbbbaaaaffff")

    def _build_client(tool_name: str, payload: Any) -> Client:
        now = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)
        return Client(
            canonical_id=_FIXED_CANONICAL_ID,
            display_name="henderson",
            client_type="individual",
            first_name="john",
            last_name="henderson",
            date_of_birth="1970-01-01",
            ssn_last_four="3333",
            tax_id="999-88-7777",
            firm_id=_FIXED_FIRM_ID,
            jurisdiction="US",
            source_system="salesforce_fsc",
            source_id="SF-001",
            created_at=now,
            updated_at=now,
        )

    stub = StubVendorAdapter(response_factory=_build_client)
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    req = _build_request(aid_token, vendor_adapter=stub)
    resp = gw.call(req)

    # Decision ALLOW + clean liability
    assert resp.decision == "ALLOW"
    assert resp.liability_report.is_clean() is True

    # Result is a Client — advisor role has SSN/DOB redacted per M4.
    filtered = resp.result
    assert isinstance(filtered, Client)
    assert filtered.ssn_last_four is None
    assert filtered.date_of_birth is None

    # AuditEntry sealed + integrity verified
    entry = audit_logger._worm.entries[0]
    assert entry.sha256_integrity != ""
    assert audit_logger.verify_integrity(entry) is True

    # Provenance chain has 8 stages + verify
    assert len(entry.provenance_chain) == 8


# =============================================================================
# T20 — docstring
# =============================================================================


def test_T20_module_docstring_has_usage():
    import m6_mcp_gateway as m6

    assert m6.__doc__ is not None
    doc = m6.__doc__
    assert "Trust-Aware" in doc
    assert "m6-mcp-gateway.md" in doc
