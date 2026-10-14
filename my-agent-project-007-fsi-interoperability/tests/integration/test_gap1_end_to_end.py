"""
Gap 1 — Reg BI Doc Generator — Integration tests (I1..I5).

See .kiro/specs/gap1-reg-bi-doc-generator.md §3.2.

Each test wires the full generator with all Protocols stubbed via
in-memory implementations, walks the end-to-end flow, and asserts
post-conditions on audit / Smarsh / principal queue / renderer.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Callable, Iterable
from uuid import UUID, uuid4

import pytest

from m1_identity import AidClaims, ISSUER, Role
from m3_schema_registry import Client, Order, OrderStatus, ResearchBrief, ResearchSource
from m5_config_loader import (
    ConflictEntry,
    PrincipalReviewConfig,
    PrincipalReviewMode,
    RegBiConfig,
    TimeoutAction,
)

from compliance.gap1_reg_bi_doc_generator import (
    AuditWriteFailed,
    BulletConcatNarrativeClient,
    DocumentRenderer,
    FakeLLMNarrativeClient,
    GenerationInput,
    GenerationSkipped,
    InMemoryAuditClient,
    InMemoryPrincipalReviewQueue,
    InMemorySmarshClient,
    MnpiPreflightResult,
    ObligationCode,
    ProductType,
    RegBiDocGenerator,
    RegBiDocument,
    RegexMnpiFilter,
    StubMnpiFilter,
    TriggerEventType,
)

UTC = timezone.utc
_NOW = datetime(2026, 1, 1, tzinfo=UTC)
_CLIENT_ID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_FIRM_ID = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_ORDER_ID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
_DOC_ID = UUID("11111111-1111-4111-8111-111111111111")
_ENTRY_ID = UUID("22222222-2222-4222-8222-222222222222")


def _aid(
    *, registration_type: str = "dual_registered",
    archetype: str = "tier3_broker_dealer",
) -> AidClaims:
    return AidClaims(
        iss=ISSUER,
        sub="advisor-01",
        aud="007-mcp-gateway",
        exp=2_000_000_000, iat=1_700_000_000, nbf=1_700_000_000,
        jti="aid-int-0001",
        firm_id="firm-int",
        lei=None, crd_number="CRD-INT",
        archetype=archetype,
        role=Role.advisor,
        authority_scope=["*"],
        authority_excludes=[],
        registration_type=registration_type,
    )


def _client(*, client_type: str = "individual") -> Client:
    return Client(
        canonical_id=_CLIENT_ID,
        display_name="integration client",
        client_type=client_type,
        risk_tolerance="moderate",
        investment_objectives=["growth", "income"],
        time_horizon="long_term",
        firm_id=_FIRM_ID,
        jurisdiction="US",
        source_system="salesforce_fsc",
        source_id="SF-INT",
        created_at=_NOW, updated_at=_NOW,
    )


def _order() -> Order:
    return Order(
        order_id=_ORDER_ID,
        client_ref=str(_CLIENT_ID),
        account_ref="ACC-INT",
        side="buy",
        quantity=100.0,
        status=OrderStatus.DRAFT,
        commission=9.99,
        created_at=_NOW,
    )


def _brief() -> ResearchBrief:
    return ResearchBrief(
        brief_id=UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd"),
        analyst_id="analyst-01",
        rating="buy",
        summary="int summary",
        thesis="int thesis",
        catalysts=[],
        risks=[],
        sources=[ResearchSource(source_type="crm_data", description="seed")],
        pipeline_run_id="run-int",
        hitl_gates_passed=[],
        anti_fabrication_score=0.95,
        created_at=_NOW,
        trace_id="trace-int",
    )


def _cfg(
    *, narrative_model: str = "haiku",
    require_advisor_review: bool = True,
    conflict_inventory: Iterable[ConflictEntry] | None = None,
) -> RegBiConfig:
    return RegBiConfig(
        template="default",
        auto_generate=True,
        require_advisor_review=require_advisor_review,
        narrative_model=narrative_model,
        conflict_inventory=(
            list(conflict_inventory) if conflict_inventory else []
        ),
    )


def _prc(
    *, mode: PrincipalReviewMode = PrincipalReviewMode.post_use
) -> PrincipalReviewConfig:
    return PrincipalReviewConfig(
        mode=mode, sla_hours=4, timeout_action=TimeoutAction.block
    )


def _input(
    *,
    advisor: AidClaims | None = None,
    client: Client | None = None,
    config: RegBiConfig | None = None,
    principal_review_config: PrincipalReviewConfig | None = None,
    trigger: TriggerEventType = TriggerEventType.order_drafted_retail,
    product_type: ProductType | None = None,
) -> GenerationInput:
    return GenerationInput(
        trigger=trigger,
        trace_id="trace-int-0001",
        generated_at=_NOW,
        client=client or _client(),
        advisor=advisor or _aid(),
        research_brief=_brief(),
        order=_order(),
        reason_trace=(),
        config=config or _cfg(),
        principal_review_config=principal_review_config,
        product_type=product_type,
    )


def _fixed_ids() -> Callable[[], UUID]:
    iterator = iter([_DOC_ID, _ENTRY_ID] + [uuid4() for _ in range(10)])
    return lambda: next(iterator)


# =============================================================================
# I1 — End-to-end BD dual-registered APPLICABLE
# =============================================================================


def test_I1_end_to_end_bd_dual_registered_happy_path():
    audit = InMemoryAuditClient()
    smarsh = InMemorySmarshClient()
    queue = InMemoryPrincipalReviewQueue()

    gen = RegBiDocGenerator(
        narrative_client=BulletConcatNarrativeClient(),
        audit_client=audit,
        mnpi_filter=StubMnpiFilter(pass_all=True),
        principal_queue=queue,
        smarsh_client=smarsh,
        renderer=DocumentRenderer(),
        document_id_factory=_fixed_ids(),
    )
    out = gen.generate(
        _input(
            advisor=_aid(registration_type="dual_registered"),
            principal_review_config=_prc(),
        )
    )
    assert isinstance(out, RegBiDocument)
    # Audit captured 1 doc.
    assert len(audit.records_docs) == 1
    assert len(audit.records_skips) == 0
    # Smarsh captured 1 archive with rendered HTML.
    assert len(smarsh.records) == 1
    _doc, rendered = smarsh.records[0]
    assert rendered.content_type == "text/html"
    assert rendered.body.startswith(b"<!DOCTYPE html>")
    # Principal queue captured 1 entry (advisor_review_required=True
    # because require_advisor_review=True in config).
    assert len(queue.entries) == 1
    entry = queue.entries[0]
    assert entry.document_id == out.document_id
    assert entry.mode == PrincipalReviewMode.post_use


# =============================================================================
# I2 — End-to-end RIA-only → SKIP_RIA
# =============================================================================


def test_I2_end_to_end_ria_only_skip_path():
    audit = InMemoryAuditClient()
    smarsh = InMemorySmarshClient()
    queue = InMemoryPrincipalReviewQueue()

    gen = RegBiDocGenerator(
        audit_client=audit,
        mnpi_filter=StubMnpiFilter(pass_all=True),
        principal_queue=queue,
        smarsh_client=smarsh,
        renderer=DocumentRenderer(),
    )
    out = gen.generate(
        _input(
            advisor=_aid(
                registration_type="ria_only",
                archetype="tier4_independent_ria",
            ),
        )
    )
    assert isinstance(out, GenerationSkipped)
    assert len(audit.records_skips) == 1
    assert len(audit.records_docs) == 0
    assert len(smarsh.records) == 0
    assert len(queue.entries) == 0


# =============================================================================
# I3 — FakeLLM + MNPI preflight FAIL on one section
# =============================================================================


def test_I3_end_to_end_mnpi_preflight_fail_on_one_section():
    """Custom MNPI filter fails only the CARE section; others pass."""

    class SelectiveFilter:
        def preflight(self, *, bullets, claims):
            # Fail only when the bullets look like CARE (they'll contain
            # "risk tolerance" or "objectives"). Otherwise pass.
            joined = " ".join(bullets)
            if "risk tolerance" in joined.lower():
                return MnpiPreflightResult(
                    passed=False, reason="mock_fail_care"
                )
            return MnpiPreflightResult(passed=True, reason="ok")

    audit = InMemoryAuditClient()
    fake_llm = FakeLLMNarrativeClient(default="fake narrative")
    gen = RegBiDocGenerator(
        narrative_client=fake_llm,
        audit_client=audit,
        mnpi_filter=SelectiveFilter(),
        renderer=DocumentRenderer(),
    )
    out = gen.generate(_input())
    assert isinstance(out, RegBiDocument)
    assert out.any_mnpi_preflight_failed is True
    assert out.advisor_review_required is True
    # CARE narrative aborted; others populated by FakeLLM.
    assert out.care.narrative == ""
    assert out.disclosure.narrative == "fake narrative"
    # Document still written to audit.
    assert len(audit.records_docs) == 1


# =============================================================================
# I4 — FakeLLM success + renderer mini-golden
# =============================================================================


def test_I4_end_to_end_fake_llm_renderer_stable_across_runs():
    audit = InMemoryAuditClient()
    fake_llm = FakeLLMNarrativeClient(default="canned prose for I4")
    gen = RegBiDocGenerator(
        narrative_client=fake_llm,
        audit_client=audit,
        mnpi_filter=StubMnpiFilter(pass_all=True),
        renderer=DocumentRenderer(),
        document_id_factory=_fixed_ids(),
    )
    out = gen.generate(_input())
    assert isinstance(out, RegBiDocument)
    hash_1 = out.rendered_content_sha256
    assert hash_1 is not None
    # Re-run: same inputs + deterministic ID factory → same hash.
    audit2 = InMemoryAuditClient()
    gen2 = RegBiDocGenerator(
        narrative_client=FakeLLMNarrativeClient(default="canned prose for I4"),
        audit_client=audit2,
        mnpi_filter=StubMnpiFilter(pass_all=True),
        renderer=DocumentRenderer(),
        document_id_factory=_fixed_ids(),
    )
    out2 = gen2.generate(_input())
    assert isinstance(out2, RegBiDocument)
    assert out2.rendered_content_sha256 == hash_1


# =============================================================================
# I5 — Audit write failure propagates; Smarsh ran pre-audit
# =============================================================================


def test_I5_audit_failure_propagates_after_smarsh_runs():
    class RaisingAudit:
        def __init__(self):
            self.calls = 0

        def write(self, record):
            self.calls += 1
            raise RuntimeError("audit sink down")

    smarsh = InMemorySmarshClient()
    queue = InMemoryPrincipalReviewQueue()
    audit = RaisingAudit()

    gen = RegBiDocGenerator(
        narrative_client=BulletConcatNarrativeClient(),
        audit_client=audit,
        mnpi_filter=StubMnpiFilter(pass_all=True),
        principal_queue=queue,
        smarsh_client=smarsh,
        renderer=DocumentRenderer(),
    )
    with pytest.raises(AuditWriteFailed) as exc_info:
        gen.generate(
            _input(
                advisor=_aid(registration_type="bd_only"),
                principal_review_config=_prc(
                    mode=PrincipalReviewMode.post_use
                ),
            )
        )
    assert exc_info.value.reason == "audit_write_failed"
    # Smarsh ran before audit (R7.3 step 11 → 12 ordering).
    assert len(smarsh.records) == 1
    # Audit was attempted once.
    assert audit.calls == 1
    # post_use queue never reached — audit failed first.
    assert len(queue.entries) == 0
