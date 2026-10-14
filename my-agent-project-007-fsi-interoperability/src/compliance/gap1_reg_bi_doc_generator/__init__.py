"""
Gap 1 — Reg BI Doc Generator — Public API (v3).

Parent module: M10 (Audit Logger).

Deterministic Reg BI Recommendation Disclosure document assembler
(SEC 17 CFR §240.15l-1). Applicability gate + OPA-style required-
sections matrix + four-obligation populators + 7 canonical disclosures
+ M4 MNPI preflight + optional LLM narrative + deterministic HTML
renderer + SHA-256 integrity + principal-review-queue hook + Smarsh
archive hook + audit-tier write (all via injected Protocols).

Phase 3 — Python + Pydantic only. No Jinja (Phase 4). NO LLM for
compliance decisions — LLM only stitches bullets into prose. Fail-
closed: LLM/MNPI failure degrades to empty narrative + forced advisor
review; audit or Smarsh sink failure raises.

Usage:

    from compliance.gap1_reg_bi_doc_generator import (
        RegBiDocGenerator, GenerationInput, TriggerEventType,
        InMemoryAuditClient, InMemorySmarshClient,
        InMemoryPrincipalReviewQueue, DocumentRenderer,
    )

    gen = RegBiDocGenerator(
        audit_client=InMemoryAuditClient(),
        renderer=DocumentRenderer(),
        smarsh_client=InMemorySmarshClient(),
        principal_queue=InMemoryPrincipalReviewQueue(),
    )
    out = gen.generate(GenerationInput(...))

See ``.kiro/specs/gap1-reg-bi-doc-generator.md`` for the full contract.
"""

from __future__ import annotations

from compliance.gap1_reg_bi_doc_generator._types import (
    ApplicabilityResult,
    InsufficientBulletsError,
    ObligationCode,
    TriggerEventType,
    UnsupportedTriggerError,
)
from compliance.gap1_reg_bi_doc_generator.applicability import (
    evaluate_applicability,
)
from compliance.gap1_reg_bi_doc_generator.audit_client import (
    AuditClient,
    AuditWriteFailed,
    InMemoryAuditClient,
)
from compliance.gap1_reg_bi_doc_generator.disclosures import (
    CANONICAL_DISCLOSURE_NAMES,
    BestInterestRationale,
    CanonicalDisclosures,
    ConflictInventoryDisclosure,
    DisciplineHistoryLink,
    FeeItem,
    FeesAndCompensation,
    Limitations,
    MonitoringFrequency,
    ProductScope,
)
from compliance.gap1_reg_bi_doc_generator.document import (
    DOCUMENT_SCHEMA_VERSION,
    GenerationInput,
    GenerationSkipped,
    ProductType,
    REDACTION_TOKEN,
    RegBiDocument,
    RegBiSection,
)
from compliance.gap1_reg_bi_doc_generator.generator import (
    RegBiDocGenerator,
)
from compliance.gap1_reg_bi_doc_generator.mnpi_preflight import (
    MnpiFilter,
    MnpiPreflightResult,
    RegexMnpiFilter,
    StubMnpiFilter,
)
from compliance.gap1_reg_bi_doc_generator.narrative import (
    POPULATED_BY_RE,
    BulletConcatNarrativeClient,
    FakeLLMNarrativeClient,
    NarrativeClient,
    StubNarrativeClient,
)
from compliance.gap1_reg_bi_doc_generator.obligations import (
    REQUIRED_SECTIONS_MATRIX,
    OpaRequirementsResolver,
    RequiredSectionsPredicate,
    RequiredSectionsRule,
    ResolvedRequirements,
)
from compliance.gap1_reg_bi_doc_generator.principal_queue import (
    InMemoryPrincipalReviewQueue,
    PrincipalReviewQueue,
    PrincipalReviewQueueEntry,
)
from compliance.gap1_reg_bi_doc_generator.renderer import (
    DocumentRenderer,
    RenderedDocument,
    RendererNotImplemented,
)
from compliance.gap1_reg_bi_doc_generator.smarsh_hook import (
    InMemorySmarshClient,
    SmarshArchiveClient,
    SmarshArchiveFailed,
)

__all__ = [
    # Enums + errors
    "TriggerEventType",
    "ObligationCode",
    "ApplicabilityResult",
    "ProductType",
    "UnsupportedTriggerError",
    "InsufficientBulletsError",
    # Applicability
    "evaluate_applicability",
    # Document + input
    "GenerationInput",
    "GenerationSkipped",
    "RegBiSection",
    "RegBiDocument",
    "DOCUMENT_SCHEMA_VERSION",
    "REDACTION_TOKEN",
    # Narrative
    "NarrativeClient",
    "StubNarrativeClient",
    "BulletConcatNarrativeClient",
    "FakeLLMNarrativeClient",
    "POPULATED_BY_RE",
    # Audit
    "AuditClient",
    "InMemoryAuditClient",
    "AuditWriteFailed",
    # MNPI preflight
    "MnpiFilter",
    "StubMnpiFilter",
    "RegexMnpiFilter",
    "MnpiPreflightResult",
    # OPA matrix
    "OpaRequirementsResolver",
    "ResolvedRequirements",
    "REQUIRED_SECTIONS_MATRIX",
    "RequiredSectionsRule",
    "RequiredSectionsPredicate",
    # Renderer
    "DocumentRenderer",
    "RenderedDocument",
    "RendererNotImplemented",
    # Principal queue
    "PrincipalReviewQueue",
    "InMemoryPrincipalReviewQueue",
    "PrincipalReviewQueueEntry",
    # Smarsh
    "SmarshArchiveClient",
    "InMemorySmarshClient",
    "SmarshArchiveFailed",
    # Canonical disclosures
    "ConflictInventoryDisclosure",
    "BestInterestRationale",
    "FeeItem",
    "FeesAndCompensation",
    "ProductScope",
    "MonitoringFrequency",
    "DisciplineHistoryLink",
    "Limitations",
    "CanonicalDisclosures",
    "CANONICAL_DISCLOSURE_NAMES",
    # Generator
    "RegBiDocGenerator",
]
