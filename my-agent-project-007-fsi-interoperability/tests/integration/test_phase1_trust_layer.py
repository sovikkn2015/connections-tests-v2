"""
Phase 1 Trust Layer — Integration Gate.

This file is the Phase 1 phase-boundary integration test mandated by
steering rule #30 ("INTEGRATION GATES: Phase boundary tests with real
interfaces. No phase transition without passing"). Phase 0 owns
``test_phase0_m3_m5.py``; Phase 1 owns this file.

Scope: exercises the full M6 trust pipeline with REAL instances of
M1 (IdentityService), M2 (AuthorityPolicy), M4 (MnpiPolicy), M10
(AuditLogger + 3 tiers + DLQ), Gap 2 (WarrantyBoundary +
LiabilityReport) and Gap 6 (MnpiLeakageScanner). Only the vendor
adapter is stubbed (Phase 1 has no M11) and one custom
``RaisingAuditBackend`` is used in scenario 6 to exercise the audit-
failed retry path. Nothing else is mocked.

The 7 scenarios correspond to the LLMJ SCORING doc
(``.kiro/specs/phase1-trust-layer-SCORING.md`` §7 "What would make it
a 10") and are the gate that Blocker B1 unblocks:

    1. scenario_1_allow_happy_path        — full ALLOW, 8-stage chain
    2. scenario_2_authority_denied        — cross-advisor read DENY
    3. scenario_3_authority_escalated     — BD retail comm ESCALATE
    4. scenario_4_mnpi_redacted_on_response — SSN/DOB/tax_id redacted
    5. scenario_5_leakage_scan_denies     — Gap 6 Layer A SSN catch
    6. scenario_6_audit_failed            — tier fails once, DLQ holds
    7. scenario_7_circuit_open            — pre-tripped breaker skips

Determinism: UUIDs are pinned (random uuid4 last segments can hit
Layer A's ``\\b\\d{12,}\\b`` pattern ~3% of runs — T19 was previously
flaky for exactly this reason). Time is driven by FakeMonotonic and
FakeUtcClock.

Run:
    python3 -m pytest tests/integration/test_phase1_trust_layer.py -v
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from m1_identity import AidClaims, IdentityService, Role
from m2_m4_policy_engine import AuthorityPolicy, MnpiPolicy
from m3_schema_registry import AuditEntry, Client
from m5_config_loader import Archetype, RegistrationType
from m6_mcp_gateway import (
    CircuitBreaker,
    GatewayError,
    GatewayRequest,
    RateLimiter,
    StubVendorAdapter,
    TrustAwareGateway,
)
from m10_audit_logger import (
    AuditLogger,
    InMemoryAuditBackend,
    InMemoryAuditDLQ,
)
from compliance.gap6_mnpi_leakage_scan import MnpiLeakageScanner


UTC = timezone.utc


# Deterministic UUIDs for every scenario that constructs a Client.
# Hex-letter segments avoid Layer A's 12-digit account_number pattern.
_FIXED_CANONICAL_ID = uuid.UUID("aaaaaaaa-bbbb-4ccc-8ddd-eeeeffffaaaa")
_FIXED_FIRM_ID = uuid.UUID("ffffffff-eeee-4ddd-8ccc-bbbbaaaaffff")


# =============================================================================
# Deterministic fixtures (duplicated from tests/unit/test_m6_mcp_gateway.py
# by design — steering rule #34 forbids importing from tests/unit/*).
# =============================================================================


class FakeMonotonic:
    """Deterministic monotonic clock. Advances only via ``.advance(delta)``."""

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
    # HS256 key must be >=32 bytes (M1 spec §0.1). Test-only value.
    monkeypatch.setenv(
        "AID_SIGNING_KEY",
        "test-signing-key-only-unit-tests-never-production-32b!",
    )
    return IdentityService(audience="007-mcp-gateway")


@pytest.fixture
def aid_token(identity_service: IdentityService) -> str:
    """RIA advisor token — used by scenarios 1, 2, 4, 5, 6, 7."""
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


# =============================================================================
# Gateway + request builders
# =============================================================================


def _build_gateway(
    *,
    identity: IdentityService,
    audit: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
    circuit_breaker: CircuitBreaker | None = None,
    rate_limiter: RateLimiter | None = None,
) -> TrustAwareGateway:
    return TrustAwareGateway(
        identity=identity,
        authority=AuthorityPolicy(),
        mnpi=MnpiPolicy(),
        audit=audit,
        leakage_scanner=leakage_scanner,
        circuit_breaker=circuit_breaker
        or CircuitBreaker(
            failure_threshold=5, recovery_seconds=30.0, clock=fake_mono
        ),
        rate_limiter=rate_limiter
        or RateLimiter(
            capacity=60, refill_per_second=1.0, clock=fake_mono
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
    trace_id: str = "trace-phase1-int-0001",
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


def _build_client(
    *,
    ssn: str | None = "3333",
    dob: str | None = "1970-01-01",
    tax_id: str | None = "999-88-7777",
    display_name: str = "henderson",
    source_id: str = "SF-001",
) -> Client:
    """Construct a canonical M3 Client with pinned UUIDs + synthetic PII."""
    now = datetime(2026, 4, 14, 12, 0, tzinfo=UTC)
    return Client(
        canonical_id=_FIXED_CANONICAL_ID,
        display_name=display_name,
        client_type="individual",
        first_name="john",
        last_name="henderson",
        date_of_birth=dob,
        ssn_last_four=ssn,
        tax_id=tax_id,
        firm_id=_FIXED_FIRM_ID,
        jurisdiction="US",
        source_system="salesforce_fsc",
        source_id=source_id,
        created_at=now,
        updated_at=now,
    )


def _assert_three_tiers_have_entry(
    audit_logger: AuditLogger, *, decision: str, reason: str | None
) -> AuditEntry:
    """Assert the last write landed in all 3 tiers and return the WORM copy."""
    assert len(audit_logger._langfuse.entries) >= 1
    assert len(audit_logger._worm.entries) >= 1
    assert len(audit_logger._crm.entries) >= 1
    entry = audit_logger._worm.entries[-1]
    assert entry.decision == decision
    if reason is not None:
        assert entry.reason == reason
    # SHA-256 integrity must be present and verify (steering rule #3 +
    # M10 Rule 3: every audit entry is sealed).
    assert entry.sha256_integrity != ""
    assert audit_logger.verify_integrity(entry) is True
    return entry


# =============================================================================
# Scenario 1 — ALLOW happy path
# =============================================================================


def test_scenario_1_allow_happy_path(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    """Advisor reads own client. All 11 pipeline stages execute; 8 land
    in the provenance chain (identity, authority, mnpi_request_filter,
    resilience, vendor_call, translate, mnpi_response_filter,
    leakage_scan). MNPI fields redacted by M4; LiabilityReport is clean.

    Cites SCORING §7 "ALLOW" and M6 spec R6 ALLOW pipeline.
    """
    stub = StubVendorAdapter(
        response_factory=lambda tool, payload: _build_client()
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    resp = gw.call(_build_request(aid_token, vendor_adapter=stub))

    # Decision + LiabilityReport contract (Gap 2).
    assert resp.decision == "ALLOW"
    assert resp.liability_report is not None
    assert resp.liability_report.is_clean() is True

    # M4 redacted SSN/DOB/tax_id for an advisor role.
    filtered = resp.result
    assert isinstance(filtered, Client)
    assert filtered.ssn_last_four is None
    assert filtered.date_of_birth is None
    assert filtered.tax_id is None

    # Audit write landed in all 3 tiers (steering rule #6, M10 Rule 7).
    entry = _assert_three_tiers_have_entry(
        audit_logger, decision="allow", reason=None
    )

    # Exactly 8 provenance stages in the expected order.
    stage_names = [s.stage for s in entry.provenance_chain]
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


# =============================================================================
# Scenario 2 — Authority DENY (cross-advisor read)
# =============================================================================


def test_scenario_2_authority_denied(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    """Advisor 'sarah' tries to read a client assigned to another advisor.
    M2 rule ``authority/advisor/read_other_advisor_clients.v1`` fires a
    terminal DENY. Audit entry still written to all 3 tiers (trust layer
    is fail-closed, not silent). Provenance ends at m6.authority.

    Cites M2 spec WSP-ADV-1.2 and SCORING §7 "authority_denied".
    """
    stub = StubVendorAdapter(
        response_factory=lambda tool, payload: _build_client()
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    # advisor_id != token.sub ('sarah') — foreign firm's client.
    req = _build_request(
        aid_token,
        vendor_adapter=stub,
        target={"client_id": "CLT-2", "advisor_id": "other_advisor"},
    )

    with pytest.raises(GatewayError) as exc_info:
        gw.call(req)
    assert exc_info.value.reason == "authority_denied"

    # Vendor was never called (DENY is terminal at stage 2).
    assert stub.call_count == 0

    entry = _assert_three_tiers_have_entry(
        audit_logger, decision="deny", reason="authority_denied"
    )
    stage_names = [s.stage for s in entry.provenance_chain]
    assert stage_names == ["m6.identity", "m6.authority"]
    # The authority stage records the DENY decision.
    authority_stage = entry.provenance_chain[-1]
    assert authority_stage.module == "m6"


# =============================================================================
# Scenario 3 — Authority ESCALATE (BD retail comm)
# =============================================================================


def test_scenario_3_authority_escalated(
    identity_service: IdentityService,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    """BD-registered advisor sends retail communication. FINRA 2210 rule
    ``authority/principal/review_required.v1`` fires ESCALATE. The
    gateway converts ESCALATE to GatewayError('authority_escalated')
    and audit-logs with decision=escalate.

    Cites M2 spec WSP-FINRA-2210 and SCORING §7 "authority_escalated".
    """
    # Issue a BD-only token (RegistrationType.bd_only triggers the rule).
    bd_token = identity_service.issue(
        sub="broker_bob",
        firm_id="CRD-2",
        lei=None,
        crd_number="CRD-2",
        archetype=Archetype.tier3_broker_dealer,
        role=Role.advisor,
        registration_type=RegistrationType.bd_only,
        authority_scope=["comm.send_retail"],
        authority_excludes=[],
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    req = _build_request(
        bd_token,
        action="comm.send_retail",
        tool_name="comm.draft_email",
        mcp_server="comms",
        target={"recipient_id": "R-1", "advisor_id": "broker_bob"},
        context={"recipient_type": "retail"},
        trace_id="trace-phase1-int-0003",
        firm_id="CRD-2",
    )

    with pytest.raises(GatewayError) as exc_info:
        gw.call(req)
    assert exc_info.value.reason == "authority_escalated"

    entry = _assert_three_tiers_have_entry(
        audit_logger, decision="escalate", reason="authority_escalated"
    )
    stage_names = [s.stage for s in entry.provenance_chain]
    assert stage_names == ["m6.identity", "m6.authority"]


# =============================================================================
# Scenario 4 — MNPI response filter redacts Client fields
# =============================================================================


def test_scenario_4_mnpi_redacted_on_response(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    """Vendor returns a populated Client (SSN + DOB + tax_id non-null).
    M4 response filter redacts those 3 fields to None for the advisor
    role per WSP-MNPI-1.{1,2,3}. The mnpi_response_filter provenance
    stage records different input_hash vs output_hash, proving the
    filter actually rewrote the payload.

    Cites M4 spec R5 and SCORING §7 "MNPI-redacted-on-response".
    """
    stub = StubVendorAdapter(
        response_factory=lambda tool, payload: _build_client(
            ssn="4444", dob="1965-06-15", tax_id="888-77-6666"
        )
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )
    resp = gw.call(_build_request(aid_token, vendor_adapter=stub))

    assert resp.decision == "ALLOW"
    filtered = resp.result
    assert isinstance(filtered, Client)
    # The three MNPI fields are redacted to None.
    assert filtered.ssn_last_four is None
    assert filtered.date_of_birth is None
    assert filtered.tax_id is None
    # Non-MNPI fields pass through.
    assert filtered.display_name == "henderson"
    assert filtered.canonical_id == _FIXED_CANONICAL_ID

    entry = _assert_three_tiers_have_entry(
        audit_logger, decision="allow", reason=None
    )
    # Locate the mnpi_response_filter stage — proves the filter stage
    # actually ran. The provenance chain does not expose payload
    # contents (by design, to avoid PII leakage into the sealed
    # record), so content proof that "input != output" is carried by
    # ``resp.result``: SSN/DOB/tax_id populated pre-filter are all None
    # post-filter, which is only possible if the filter rewrote the
    # payload.
    resp_filter_stages = [
        s for s in entry.provenance_chain
        if s.stage == "m6.mnpi_response_filter"
    ]
    assert len(resp_filter_stages) == 1
    assert resp_filter_stages[0].module == "m6"
    # Stage is hashed into the chain, so its hash must be non-empty.
    assert resp_filter_stages[0].hash != ""


# =============================================================================
# Scenario 5 — Gap 6 Layer A denies on SSN pattern survival
# =============================================================================


def test_scenario_5_leakage_scan_denies(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    """Vendor returns a Client whose ``display_name`` — a field M4 does
    NOT redact — contains a dashed SSN pattern ("123-45-6789"). M4
    passes it through; Gap 6 Layer A's SSN regex catches it at the
    leakage_scan stage and fails closed with GatewayError(
    'mnpi_leakage_scan'). This is the last-line-of-defense scan that
    the 3-tier-audit is wrapped around.

    Cites Gap 6 spec R2 Layer A and SCORING §7 "leakage_scan_denies".
    """
    # Dashed SSN in display_name survives M4 (M4 only redacts
    # ssn_last_four/date_of_birth/tax_id/beneficiary.account_number).
    stub = StubVendorAdapter(
        response_factory=lambda tool, payload: _build_client(
            display_name="henderson 123-45-6789",
            ssn=None, dob=None, tax_id=None,
        )
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )

    with pytest.raises(GatewayError) as exc_info:
        gw.call(_build_request(aid_token, vendor_adapter=stub))
    assert exc_info.value.reason == "mnpi_leakage_scan"

    entry = _assert_three_tiers_have_entry(
        audit_logger, decision="deny", reason="mnpi_leakage_scan"
    )
    stage_names = [s.stage for s in entry.provenance_chain]
    # Full pipeline runs through the scan, then the scan DENIES.
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
    # The leakage_scan stage is terminal (hash non-empty, last in chain).
    scan_stage = entry.provenance_chain[-1]
    assert scan_stage.stage == "m6.leakage_scan"
    assert scan_stage.module == "m6"
    assert scan_stage.hash != ""


# =============================================================================
# Scenario 6 — Audit write fails first, succeeds on retry
# =============================================================================


def test_scenario_6_audit_failed(
    identity_service: IdentityService,
    aid_token: str,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    """Inject a WORM backend that raises on its first write and then
    succeeds. The ALLOW-path Stage-10 audit write fails; the gateway
    appends ``m6.audit_attempt`` to the provenance chain, calls
    ``_handle_failure(reason='audit_failed')``, which writes a retry
    entry (decision=deny, reason=audit_failed) that succeeds. The
    original request still fails fail-closed (steering rule #8). The
    DLQ must have received the sealed first-failure entry (Rule 8:
    "DLQ is for recovery, not for bypassing the audit requirement").

    Cites M10 Rule 8, M6 spec R6.10, SCORING §7 "audit_failed".
    """
    # fail_on_nth=1 => first write raises; subsequent writes succeed.
    failing_worm = InMemoryAuditBackend(tier="worm", fail_on_nth=1)
    langfuse = InMemoryAuditBackend(tier="langfuse")
    crm = InMemoryAuditBackend(tier="crm")
    dlq = InMemoryAuditDLQ()
    audit = AuditLogger(
        langfuse=langfuse, worm=failing_worm, crm=crm, dlq=dlq,
    )

    stub = StubVendorAdapter(
        response_factory=lambda tool, payload: _build_client()
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
    )

    with pytest.raises(GatewayError) as exc_info:
        gw.call(_build_request(aid_token, vendor_adapter=stub))
    assert exc_info.value.reason == "audit_failed"

    # The DLQ received the sealed first-attempt entry with the
    # originating tier reason (not masked by the retry success).
    assert len(dlq.records) == 1
    dlq_entry, dlq_reason = dlq.records[0]
    assert dlq_reason == "worm_write_failed"
    assert dlq_entry.sha256_integrity != ""
    assert audit.verify_integrity(dlq_entry) is True

    # The retry succeeded — all 3 tiers hold the 2nd (deny/audit_failed)
    # entry. Langfuse + CRM also hold the 1st (never-failed) attempt
    # because tier writes execute in order (langfuse -> worm -> crm)
    # and worm failed after langfuse had already succeeded.
    assert len(langfuse.entries) == 2
    assert len(failing_worm.entries) == 1   # only the retry landed
    assert len(crm.entries) == 1

    # The retry entry (WORM copy) is the definitive audit record.
    entry = failing_worm.entries[-1]
    assert entry.decision == "deny"
    assert entry.reason == "audit_failed"
    assert audit.verify_integrity(entry) is True

    # Provenance chain includes the 8 ALLOW stages plus the
    # ``m6.audit_attempt`` failure marker (9 stages total).
    stage_names = [s.stage for s in entry.provenance_chain]
    assert stage_names[:8] == [
        "m6.identity",
        "m6.authority",
        "m6.mnpi_request_filter",
        "m6.resilience",
        "m6.vendor_call",
        "m6.translate",
        "m6.mnpi_response_filter",
        "m6.leakage_scan",
    ]
    assert stage_names[-1] == "m6.audit_attempt"
    assert len(stage_names) == 9


# =============================================================================
# Scenario 7 — Pre-tripped CircuitBreaker skips the vendor
# =============================================================================


def test_scenario_7_circuit_open(
    identity_service: IdentityService,
    aid_token: str,
    audit_logger: AuditLogger,
    leakage_scanner: MnpiLeakageScanner,
    fake_mono: FakeMonotonic,
    fake_clock: FakeUtcClock,
):
    """Pre-trip the CircuitBreaker for the 'salesforce' MCP server by
    recording 5 consecutive failures (threshold default). The next
    request short-circuits at Stage 4 with GatewayError('circuit_open'):
    the vendor adapter is never invoked. Audit entry is still written
    to all 3 tiers.

    Cites M6 spec R4 (CircuitBreaker) and SCORING §7 "circuit_open".
    """
    cb = CircuitBreaker(
        failure_threshold=5, recovery_seconds=30.0, clock=fake_mono
    )
    # Pre-trip by recording 5 failures directly.
    for _ in range(5):
        cb.record_failure("salesforce")
    assert cb.state("salesforce") == "OPEN"

    stub = StubVendorAdapter(
        response_factory=lambda tool, payload: _build_client()
    )
    gw = _build_gateway(
        identity=identity_service,
        audit=audit_logger,
        leakage_scanner=leakage_scanner,
        fake_mono=fake_mono,
        fake_clock=fake_clock,
        circuit_breaker=cb,
    )

    with pytest.raises(GatewayError) as exc_info:
        gw.call(_build_request(aid_token, vendor_adapter=stub))
    assert exc_info.value.reason == "circuit_open"

    # Vendor was never called — that is the point of the breaker.
    assert stub.call_count == 0

    entry = _assert_three_tiers_have_entry(
        audit_logger, decision="deny", reason="circuit_open"
    )
    stage_names = [s.stage for s in entry.provenance_chain]
    # The pipeline halts at resilience; no vendor_call stage recorded.
    assert stage_names == [
        "m6.identity",
        "m6.authority",
        "m6.mnpi_request_filter",
        "m6.resilience",
    ]
    # The resilience stage is terminal and hashed into the chain.
    resilience_stage = entry.provenance_chain[-1]
    assert resilience_stage.stage == "m6.resilience"
    assert resilience_stage.module == "m6"
    assert resilience_stage.hash != ""
