"""
Gap 1 — Deterministic HTML renderer.

See .kiro/specs/gap1-reg-bi-doc-generator.md R5b.

Contract:
    - ``render_html(document) -> RenderedDocument``.
    - Byte-identical output across two calls on the same document.
    - Every variable passes through ``html.escape(quote=True)`` (XSS).
    - UTF-8 encoded; ``content_sha256`` = SHA-256 hex of the body
      bytes.
    - Body <= 2 MiB.
    - ``render_pdf`` raises ``RendererNotImplemented``.

Phase 3 is pure Python string assembly — NO Jinja. Jinja integration
is deferred to Phase 4.
"""

from __future__ import annotations

import hashlib
import html
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from compliance.gap1_reg_bi_doc_generator._types import ObligationCode
from compliance.gap1_reg_bi_doc_generator.disclosures import (
    CANONICAL_DISCLOSURE_NAMES,
    CanonicalDisclosures,
)
from compliance.gap1_reg_bi_doc_generator.document import (
    RegBiDocument,
    RegBiSection,
    _scrub_pii,
)

# =============================================================================
# Errors
# =============================================================================


class RendererNotImplemented(NotImplementedError):
    """Raised by ``render_pdf`` until Phase 4."""


# =============================================================================
# RenderedDocument (R5b.2)
# =============================================================================

_MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 MiB


class RenderedDocument(BaseModel):
    """Frozen rendered document wire format."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    content_type: Literal["text/html", "application/pdf"]
    body: bytes = Field(max_length=_MAX_BODY_BYTES)
    content_sha256: str = Field(min_length=64, max_length=64)
    rendered_at: datetime

    @field_validator("content_sha256")
    @classmethod
    def _validate_hex(cls, v: str) -> str:
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError(
                "content_sha256 must be 64 lowercase hex chars"
            )
        return v

    @field_validator("rendered_at")
    @classmethod
    def _require_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("rendered_at must be timezone-aware")
        return v


# =============================================================================
# DocumentRenderer (R5b.1)
# =============================================================================


def _esc(s: object) -> str:
    """Scrub PII then HTML-escape (defence-in-depth, R5.2 checkpoint 4)."""
    text = str(s) if not isinstance(s, str) else s
    return html.escape(_scrub_pii(text), quote=True)


def _render_section(section: RegBiSection) -> str:
    """Render one obligation section."""
    lines: list[str] = []
    lines.append(
        f"<section class=\"obligation\" "
        f"id=\"obl-{_esc(section.obligation_code.value)}\">"
    )
    lines.append(
        f"<h2>{_esc(section.obligation_code.value.upper())}</h2>"
    )
    lines.append(
        f"<p class=\"populated-by\">{_esc(section.populated_by)}</p>"
    )
    lines.append("<ul class=\"bullets\">")
    for bullet in section.bullets:
        lines.append(f"<li>{_esc(bullet)}</li>")
    lines.append("</ul>")
    if section.narrative:
        lines.append(
            f"<p class=\"narrative\">{_esc(section.narrative)}</p>"
        )
    lines.append(
        f"<p class=\"force-review\">"
        f"force_review={_esc(str(section.force_review).lower())}</p>"
    )
    lines.append("</section>")
    return "\n".join(lines)


def _render_canonical_disclosures(
    disclosures: CanonicalDisclosures,
) -> str:
    """Render the 7 canonical disclosure types in deterministic order."""
    lines: list[str] = []
    lines.append("<section class=\"disclosures\">")
    lines.append("<h2>CANONICAL DISCLOSURES</h2>")

    for name in CANONICAL_DISCLOSURE_NAMES:
        lines.append(f"<section class=\"disclosure-{_esc(name)}\">")
        lines.append(f"<h3>{_esc(name)}</h3>")

        if name == "conflict_inventory":
            lines.append("<ul>")
            for entry in disclosures.conflict_inventory.entries:
                lines.append(
                    "<li>"
                    f"<span class=\"type\">{_esc(entry.type)}</span>: "
                    f"<span class=\"desc\">{_esc(entry.description)}</span> "
                    f"(<span class=\"mit\">{_esc(entry.mitigation)}</span>)"
                    "</li>"
                )
            lines.append("</ul>")

        elif name == "best_interest_rationale":
            bir = disclosures.best_interest_rationale
            lines.append(
                f"<p class=\"obj\">{_esc(bir.objectives_alignment)}</p>"
            )
            lines.append(
                f"<p class=\"risk\">{_esc(bir.risk_alignment)}</p>"
            )
            lines.append(
                f"<p class=\"horizon\">{_esc(bir.time_horizon_alignment)}</p>"
            )
            if bir.summary:
                lines.append(
                    f"<p class=\"summary\">{_esc(bir.summary)}</p>"
                )

        elif name == "fees_and_compensation":
            lines.append("<ul>")
            for item in disclosures.fees_and_compensation.items:
                amount_str = (
                    f"${item.amount:.2f}"
                    if item.amount is not None
                    else "n/a"
                )
                lines.append(
                    "<li>"
                    f"<span class=\"source\">{_esc(item.source)}</span> "
                    f"<span class=\"type\">{_esc(item.fee_type)}</span> "
                    f"<span class=\"amount\">{_esc(amount_str)}</span> "
                    f"<span class=\"basis\">{_esc(item.basis)}</span>: "
                    f"<span class=\"desc\">{_esc(item.description)}</span>"
                    "</li>"
                )
            lines.append("</ul>")

        elif name == "product_scope":
            lines.append(
                f"<p>{_esc(disclosures.product_scope.scope)}</p>"
            )

        elif name == "monitoring_frequency":
            lines.append(
                f"<p>{_esc(disclosures.monitoring_frequency.cadence)}</p>"
            )

        elif name == "discipline_history_link":
            url = disclosures.discipline_history_link.url
            if url:
                lines.append(
                    f"<p><a href=\"{_esc(url)}\">{_esc(url)}</a></p>"
                )
            else:
                lines.append("<p class=\"empty\">n/a</p>")

        elif name == "limitations":
            lines.append("<ul>")
            for entry in disclosures.limitations.entries:
                lines.append(f"<li>{_esc(entry)}</li>")
            lines.append("</ul>")

        lines.append("</section>")

    lines.append("</section>")
    return "\n".join(lines)


def _render_header(document: RegBiDocument) -> str:
    lines = [
        "<section class=\"header\">",
        "<h1>Reg BI Recommendation Disclosure</h1>",
        f"<p>document_id={_esc(document.document_id)}</p>",
        f"<p>trace_id={_esc(document.trace_id)}</p>",
        f"<p>generated_at={_esc(document.generated_at.isoformat())}</p>",
        f"<p>trigger={_esc(document.trigger.value)}</p>",
        f"<p>client_ref={_esc(document.client_ref)}</p>",
        f"<p>advisor_sub={_esc(document.advisor_sub)}</p>",
        f"<p>firm_id={_esc(document.firm_id)}</p>",
        f"<p>registration_type={_esc(document.registration_type.value)}</p>",
        f"<p>schema_version={_esc(document.document_schema_version)}</p>",
        "</section>",
    ]
    return "\n".join(lines)


def _render_applicability_trace(document: RegBiDocument) -> str:
    lines = [
        "<section class=\"applicability\">",
        "<h2>APPLICABILITY</h2>",
        f"<p>is_retail={_esc(str(document.is_retail).lower())}</p>",
        "<ul class=\"matched-rules\">",
    ]
    for rule in document.matched_rules:
        lines.append(f"<li>{_esc(rule)}</li>")
    lines.append("</ul>")
    lines.append("<ul class=\"wsp-sections\">")
    for wsp in document.matched_wsp_sections:
        lines.append(f"<li>{_esc(wsp)}</li>")
    lines.append("</ul>")
    lines.append("<ul class=\"required-disclosures\">")
    for name in document.required_disclosures:
        lines.append(f"<li>{_esc(name)}</li>")
    lines.append("</ul>")
    lines.append("</section>")
    return "\n".join(lines)


def _render_signatures(document: RegBiDocument) -> str:
    lines = [
        "<section class=\"signatures\">",
        "<h2>COMPLIANCE SIGNATURES</h2>",
        f"<p>advisor_review_required="
        f"{_esc(str(document.advisor_review_required).lower())}</p>",
        f"<p>llm_narrative_failed="
        f"{_esc(str(document.llm_narrative_failed).lower())}</p>",
        f"<p>any_mnpi_preflight_failed="
        f"{_esc(str(document.any_mnpi_preflight_failed).lower())}</p>",
        f"<p>narrative_model_configured="
        f"{_esc(document.narrative_model_configured)}</p>",
        "</section>",
    ]
    return "\n".join(lines)


class DocumentRenderer:
    """Deterministic HTML renderer for RegBiDocument.

    Pure Python. No templating library. Section order is fixed:
    header → applicability trace → 4 obligations (DISCLOSURE, CARE,
    COI, COMPLIANCE) → 7 canonical disclosures → signatures.
    """

    def render_html(self, document: RegBiDocument) -> RenderedDocument:
        body_str = self._assemble_html(document)
        body = body_str.encode("utf-8")
        if len(body) > _MAX_BODY_BYTES:
            raise ValueError(
                f"rendered body exceeds {_MAX_BODY_BYTES}-byte cap"
            )
        digest = hashlib.sha256(body).hexdigest()
        return RenderedDocument(
            content_type="text/html",
            body=body,
            content_sha256=digest,
            rendered_at=document.generated_at,
        )

    def render_pdf(self, document: RegBiDocument) -> RenderedDocument:
        raise RendererNotImplemented("pdf_deferred_phase4")

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------

    def _assemble_html(self, document: RegBiDocument) -> str:
        parts: list[str] = []
        parts.append("<!DOCTYPE html>")
        parts.append("<html lang=\"en\">")
        parts.append("<head>")
        parts.append("<meta charset=\"utf-8\"/>")
        parts.append("<title>Reg BI Recommendation Disclosure</title>")
        parts.append("</head>")
        parts.append("<body>")

        parts.append(_render_header(document))
        parts.append(_render_applicability_trace(document))

        # Four obligations in fixed order (R5b.1).
        for code in (
            ObligationCode.DISCLOSURE,
            ObligationCode.CARE,
            ObligationCode.COI,
            ObligationCode.COMPLIANCE,
        ):
            section: RegBiSection = getattr(document, code.value)
            parts.append(_render_section(section))

        parts.append(
            _render_canonical_disclosures(document.canonical_disclosures)
        )
        parts.append(_render_signatures(document))

        parts.append("</body>")
        parts.append("</html>")

        return "\n".join(parts)
