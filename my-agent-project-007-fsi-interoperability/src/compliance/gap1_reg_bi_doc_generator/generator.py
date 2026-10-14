"""
Gap 1 — RegBiDocGenerator orchestrator (v3).

Runs the applicability gate, resolves the OPA-style required-sections
matrix, invokes the four deterministic obligation populators, builds
the 7 canonical disclosures, gates every narrative stitch behind the
M4 MNPI preflight, optionally stitches LLM prose, renders HTML,
optionally archives to Smarsh, writes to M10 audit, and emits a
principal-review-queue entry when gated.

See .kiro/specs/gap1-reg-bi-doc-generator.md R7.

Fail-closed surfaces (the three raise paths per R7.4):
    1. ``AuditWriteFailed`` — audit sink raised.
    2. ``SmarshArchiveFailed`` — Smarsh sink raised.
    3. ``InsufficientBulletsError`` — populator floor violated.

Everything else (LLM failure, MNPI preflight fail, PII in narrative)
degrades to empty narrative + ``advisor_review_required=True``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional, Union
from uuid import UUID, uuid4

from m5_config_loader import (
    PrincipalReviewConfig,
    PrincipalReviewMode,
    RegistrationType,
)

from compliance.gap1_reg_bi_doc_generator._types import (
    ApplicabilityResult,
    ObligationCode,
)
from compliance.gap1_reg_bi_doc_generator.applicability import (
    evaluate_applicability,
)
from compliance.gap1_reg_bi_doc_generator.audit_client import (
    AuditClient,
    AuditWriteFailed,
)
from compliance.gap1_reg_bi_doc_generator.disclosures import (
    CanonicalDisclosures,
    populate_disclosures,
)
from compliance.gap1_reg_bi_doc_generator.document import (
    GenerationInput,
    GenerationSkipped,
    RegBiDocument,
    RegBiSection,
    _has_pii,
    _scrub_pii,
)
from compliance.gap1_reg_bi_doc_generator.mnpi_preflight import (
    MnpiFilter,
    MnpiPreflightResult,
    RegexMnpiFilter,
)
from compliance.gap1_reg_bi_doc_generator.narrative import (
    BulletConcatNarrativeClient,
    NarrativeClient,
    StubNarrativeClient,
)
from compliance.gap1_reg_bi_doc_generator.obligations import (
    OpaRequirementsResolver,
    POPULATORS,
    ResolvedRequirements,
)
from compliance.gap1_reg_bi_doc_generator.principal_queue import (
    PrincipalReviewQueue,
    PrincipalReviewQueueEntry,
)
from compliance.gap1_reg_bi_doc_generator.renderer import (
    DocumentRenderer,
    RenderedDocument,
)
from compliance.gap1_reg_bi_doc_generator.smarsh_hook import (
    SmarshArchiveClient,
    SmarshArchiveFailed,
)


GenerationOutcome = Union[RegBiDocument, GenerationSkipped]

# Firms that trigger BD-only wiring (Smarsh archive, principal review).
_BD_REGISTRATION_TYPES: frozenset[str] = frozenset(
    {
        RegistrationType.bd_only.value,
        RegistrationType.dual_registered.value,
    }
)


class RegBiDocGenerator:
    """Orchestrator for Reg BI document assembly (v3)."""

    def __init__(
        self,
        *,
        narrative_client: Optional[NarrativeClient] = None,
        audit_client: Optional[AuditClient] = None,
        mnpi_filter: Optional[MnpiFilter] = None,
        principal_queue: Optional[PrincipalReviewQueue] = None,
        smarsh_client: Optional[SmarshArchiveClient] = None,
        renderer: Optional[DocumentRenderer] = None,
        requirements_resolver: Optional[OpaRequirementsResolver] = None,
        document_id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        # R7.1a: Smarsh requires renderer — wire-format coupling.
        if smarsh_client is not None and renderer is None:
            raise ValueError("smarsh_requires_renderer")

        self._narrative_client = narrative_client
        self._audit_client = audit_client
        self._mnpi_filter = mnpi_filter
        self._principal_queue = principal_queue
        self._smarsh_client = smarsh_client
        self._renderer = renderer
        self._resolver = (
            requirements_resolver
            if requirements_resolver is not None
            else OpaRequirementsResolver()
        )
        self._document_id_factory = document_id_factory

    # =================================================================
    # Public API
    # =================================================================

    def generate(self, inp: GenerationInput) -> GenerationOutcome:
        """Produce a ``RegBiDocument`` or a ``GenerationSkipped``.

        Flow — see spec R7.3:

        1. Evaluate applicability.
        2. SKIP_* → build ``GenerationSkipped``, audit-write (F3 fail-
           closed), return.
        3. Resolve required-sections matrix.
        4. Build four obligations (may raise ``InsufficientBulletsError``).
        5. Build seven canonical disclosures.
        6. For each obligation section: MNPI preflight → stitch → scrub.
        7. Mint UUID.
        8. Build provisional ``RegBiDocument`` (no rendered_content_sha256).
        9. Compute ``advisor_review_required``.
        10. Render HTML (if renderer wired) → copy-with-rendered-hash.
        11. Smarsh archive (if wired + BD/dual).
        12. Audit write.
        13. Principal queue enqueue (pre_use: before audit; post_use:
            after audit — per spec §2.2).
        14. Return document.
        """
        # 1. Applicability gate.
        gate = evaluate_applicability(inp)
        if gate is not ApplicabilityResult.APPLICABLE:
            return self._emit_skip(inp, gate)

        # 3. Resolve requirements.
        resolved = self._resolver.resolve(inp)

        # 4. Obligation populators.
        populated_sections: dict[ObligationCode, RegBiSection] = {}
        force_review_any = False
        for code, populator in POPULATORS:
            section = populator(inp)  # may raise InsufficientBulletsError
            populated_sections[code] = section
            if section.force_review:
                force_review_any = True

        # 5. Canonical disclosures (deterministic).
        canonical = populate_disclosures(inp, resolved)

        # 6. Per-section: MNPI preflight → stitch → scrub.
        nc = self._resolve_narrative_client(inp)
        active_mnpi = self._resolve_mnpi_filter()

        final_sections: dict[ObligationCode, RegBiSection] = {}
        llm_failed_any = False
        any_mnpi_preflight_failed = False

        for code, section in populated_sections.items():
            narrative, llm_fail, mnpi_fail = self._stitch_with_preflight(
                nc=nc,
                mnpi=active_mnpi,
                inp=inp,
                obligation=code,
                bullets=section.bullets,
            )
            if llm_fail:
                llm_failed_any = True
            if mnpi_fail:
                any_mnpi_preflight_failed = True

            final_sections[code] = RegBiSection(
                obligation_code=section.obligation_code,
                bullets=section.bullets,
                narrative=narrative,
                populated_by=section.populated_by,
                force_review=section.force_review,
            )

        # 9. Compute advisor_review_required gate (R7.5).
        advisor_review_required = self._compute_review_gate(
            inp=inp,
            llm_failed_any=llm_failed_any,
            force_review_any=force_review_any,
            any_mnpi_preflight_failed=any_mnpi_preflight_failed,
        )

        # 7 + 8. Mint UUID and build provisional document.
        narrative_model_configured = (
            inp.config.narrative_model or "none"
        )

        document = RegBiDocument(
            document_id=self._document_id_factory(),
            trace_id=inp.trace_id,
            generated_at=inp.generated_at,
            trigger=inp.trigger,
            client_ref=inp.client.canonical_id,
            advisor_sub=inp.advisor.sub,
            firm_id=inp.advisor.firm_id,
            registration_type=RegistrationType(
                inp.advisor.registration_type
            ),
            disclosure=final_sections[ObligationCode.DISCLOSURE],
            care=final_sections[ObligationCode.CARE],
            coi=final_sections[ObligationCode.COI],
            compliance=final_sections[ObligationCode.COMPLIANCE],
            advisor_review_required=advisor_review_required,
            llm_narrative_failed=llm_failed_any,
            reason_trace_redacted=inp.reason_trace,
            research_brief_ref=(
                inp.research_brief.brief_id
                if inp.research_brief is not None
                else None
            ),
            order_ref=(
                inp.order.order_id if inp.order is not None else None
            ),
            canonical_disclosures=canonical,
            matched_rules=resolved.matched_rules,
            matched_wsp_sections=resolved.matched_wsp_sections,
            required_disclosures=tuple(
                sorted(resolved.required_disclosures)
            ),
            is_retail=resolved.is_retail,
            narrative_model_configured=narrative_model_configured,
            any_mnpi_preflight_failed=any_mnpi_preflight_failed,
            rendered_content_sha256=None,
        )

        # 10. Render HTML + rebind hash.
        rendered: Optional[RenderedDocument] = None
        if self._renderer is not None:
            rendered = self._renderer.render_html(document)
            document = document.with_rendered_hash(
                rendered.content_sha256
            )

        reg_type_str = inp.advisor.registration_type
        is_bd_firm = reg_type_str in _BD_REGISTRATION_TYPES

        # 13a. Principal queue — PRE_USE: BEFORE audit (spec §2.2, T1.47).
        should_queue = self._should_enqueue(
            inp=inp,
            is_bd_firm=is_bd_firm,
            advisor_review_required=advisor_review_required,
        )
        queue_mode: Optional[PrincipalReviewMode] = (
            inp.principal_review_config.mode
            if inp.principal_review_config is not None
            else None
        )

        if should_queue and queue_mode is PrincipalReviewMode.pre_use:
            self._enqueue(
                inp=inp,
                document=document,
                rendered=rendered,
            )

        # 11. Smarsh archive (BD/dual only).
        if (
            self._smarsh_client is not None
            and is_bd_firm
            and rendered is not None
        ):
            try:
                self._smarsh_client.archive(
                    document=document,
                    rendered=rendered,
                )
            except Exception:
                raise SmarshArchiveFailed("smarsh_archive_failed")

        # 12. Audit write.
        if self._audit_client is not None:
            try:
                self._audit_client.write(document)
            except Exception:
                raise AuditWriteFailed("audit_write_failed")

        # 13b. Principal queue — POST_USE: AFTER audit (spec §2.2, T1.48).
        if should_queue and queue_mode is PrincipalReviewMode.post_use:
            self._enqueue(
                inp=inp,
                document=document,
                rendered=rendered,
            )

        return document

    # =================================================================
    # Skip path (R7.3 step 2)
    # =================================================================

    def _emit_skip(
        self,
        inp: GenerationInput,
        gate: ApplicabilityResult,
    ) -> GenerationSkipped:
        skipped = GenerationSkipped(
            reason=gate,
            trace_id=inp.trace_id,
            trigger=inp.trigger,
        )
        if self._audit_client is not None:
            try:
                self._audit_client.write(skipped)
            except Exception:
                # F3: SKIP-path audit failure also raises.
                raise AuditWriteFailed("audit_write_failed")
        return skipped

    # =================================================================
    # Narrative + MNPI helpers
    # =================================================================

    def _resolve_narrative_client(
        self, inp: GenerationInput
    ) -> NarrativeClient:
        if self._narrative_client is not None:
            return self._narrative_client
        if (inp.config.narrative_model or "").lower() == "none":
            return StubNarrativeClient()
        return BulletConcatNarrativeClient()

    def _resolve_mnpi_filter(self) -> MnpiFilter:
        if self._mnpi_filter is not None:
            return self._mnpi_filter
        # Phase-3 default when no real M4 is wired.
        return RegexMnpiFilter()

    def _stitch_with_preflight(
        self,
        *,
        nc: NarrativeClient,
        mnpi: MnpiFilter,
        inp: GenerationInput,
        obligation: ObligationCode,
        bullets: tuple[str, ...],
    ) -> tuple[str, bool, bool]:
        """Preflight → stitch → scrub.

        Returns ``(narrative, llm_failed, mnpi_failed)``. MNPI preflight
        runs FIRST per R4b.3; if it fails, ``stitch`` is NEVER called.
        """
        # Preflight — fail-closed on exception or passed=False.
        try:
            result: MnpiPreflightResult = mnpi.preflight(
                bullets=bullets,
                claims=inp.advisor,
            )
        except Exception:
            return "", False, True

        if not result.passed:
            return "", False, True

        effective_bullets = (
            result.filtered_bullets
            if result.filtered_bullets
            else bullets
        )

        # Stitch.
        try:
            narrative = nc.stitch(
                obligation=obligation,
                bullets=effective_bullets,
                reason_trace=inp.reason_trace,
            )
        except Exception:
            return "", True, False

        if not isinstance(narrative, str):
            return "", True, False

        if len(narrative) > 2000:
            narrative = narrative[:2000]

        # Scrub check — PII post-stitch (R4.6).
        if _has_pii(narrative):
            return "", True, False

        scrubbed = _scrub_pii(narrative)
        if scrubbed != narrative:
            return "", True, False

        return narrative, False, False

    # =================================================================
    # advisor_review_required gate (R7.5)
    # =================================================================

    def _compute_review_gate(
        self,
        *,
        inp: GenerationInput,
        llm_failed_any: bool,
        force_review_any: bool,
        any_mnpi_preflight_failed: bool,
    ) -> bool:
        # Firm FLOOR — require_advisor_review=True always wins.
        if inp.config.require_advisor_review is True:
            return True

        if inp.client.risk_tolerance is None:
            return True
        if llm_failed_any:
            return True
        if any_mnpi_preflight_failed:
            return True
        if force_review_any:
            return True
        for entry in inp.reason_trace:
            if entry.startswith("REVIEW:"):
                return True
        return False

    # =================================================================
    # Principal queue (R9.4)
    # =================================================================

    def _should_enqueue(
        self,
        *,
        inp: GenerationInput,
        is_bd_firm: bool,
        advisor_review_required: bool,
    ) -> bool:
        if self._principal_queue is None:
            return False
        if not is_bd_firm:
            return False
        if inp.principal_review_config is None:
            return False
        if not advisor_review_required:
            return False
        return True

    def _enqueue(
        self,
        *,
        inp: GenerationInput,
        document: RegBiDocument,
        rendered: Optional[RenderedDocument],
    ) -> None:
        assert self._principal_queue is not None
        assert inp.principal_review_config is not None
        cfg: PrincipalReviewConfig = inp.principal_review_config
        entry = PrincipalReviewQueueEntry(
            entry_id=self._document_id_factory(),
            trace_id=inp.trace_id,
            document_id=document.document_id,
            firm_id=document.firm_id,
            registration_type=document.registration_type,
            is_retail=document.is_retail,
            mode=cfg.mode,
            sla_hours=cfg.sla_hours,
            timeout_action=cfg.timeout_action,
            rendered_content_sha256=(
                rendered.content_sha256 if rendered is not None else None
            ),
            submitted_at=_now_utc(),
        )
        self._principal_queue.enqueue(entry)


def _now_utc() -> datetime:
    """Tz-aware UTC timestamp. Kept here so tests can monkeypatch."""
    return datetime.now(tz=timezone.utc)
