"""
ReconciliationNote — M7 audit artifact emitted alongside every translation.

Per R9 / AC9.x:
- Zero PII, zero MNPI.
- `notes` content restricted to `RECONCILIATION_NOTE_SAFE_FIELDS` allow-list.
- Deterministic serialization (alphabetical keys, sorted lists).

M6 propagates `ReconciliationNote` into M10 `AuditEntry.payload` for
per-translator failure-rate aggregation (see R16 / AC16.2).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# SAFE-TOKEN ALLOW-LIST for `notes` (AC9.6)
# =============================================================================

# NI-4 fix: `schwab_ira_label_ambiguous` (was `schwab_iria` in v0.1.0).
RECONCILIATION_NOTE_SAFE_FIELDS: frozenset[str] = frozenset(
    {
        # cost-basis provenance
        "cost_basis_vendor_reported",
        "cost_basis_vendor_default_applied",
        "cost_basis_derived",
        # enum-mapping notes
        "orion_trust_label_ambiguous",
        "schwab_ira_label_ambiguous",
        "schwab_trust_label_ambiguous",
        # Schwab-specific
        "schwab_dollar_prefix_stripped",
        "schwab_market_value_excludes_accrued",
        "schwab_unrealized_gain_loss_pct_derived",
        # eMoney-specific
        "emoney_net_worth_derived",
        # Transaction
        "canonical_order_ref_preserved_in_custom_attributes",
        # SF FSC
        "salesforce_fsc_multi_picklist_split",
        "salesforce_fsc_business_account_no_contact",
        # Household
        "single_vendor_no_reconciliation",
        "multi_vendor_reconciliation_performed",
    }
)


class CostBasisSource(BaseModel):
    """Provenance for `TaxLot.cost_basis_method` — how M7 derived it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vendor_field: Optional[str] = Field(
        default=None,
        description="Vendor field name used to source the method (e.g., 'costBasisMethod').",
    )
    vendor_value: Optional[str] = Field(
        default=None,
        description=(
            "Raw vendor string (None when vendor was silent and default applied)."
        ),
    )
    canonical_value: str = Field(
        description="Canonical CostBasisMethod string value."
    )
    method_origin: Literal[
        "vendor_reported", "vendor_default", "derived"
    ] = Field(
        description="Where the method came from: vendor, default table, or derivation."
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence in the chosen method."
    )


class ReconciliationNote(BaseModel):
    """Emitted alongside every translator call. PII-free. MNPI-free."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_id: Optional[str] = Field(
        default=None,
        description="Caller-provided trace ID linking to M10 AuditEntry. M7 does NOT set this.",
    )
    vendor: str = Field(description="Vendor source system slug.")
    canonical_type: str = Field(description="Canonical type name.")
    direction: Literal["to_canonical", "from_canonical"] = Field(
        description="Translation direction."
    )
    fields_dropped: list[str] = Field(
        default_factory=list,
        description="Vendor/canonical field names dropped (subset of LOSSY_FIELDS). Sorted.",
    )
    fields_derived: list[str] = Field(
        default_factory=list,
        description="Canonical fields derived from computation/default. Sorted.",
    )
    cost_basis_source: Optional[CostBasisSource] = Field(
        default=None, description="Provenance for TaxLot.cost_basis_method."
    )
    vendor_schema_version: str = Field(
        description="Vendor API version (e.g., 'v59.0')."
    )
    translator_schema_version: str = Field(
        description="M7 translator SCHEMA_VERSION."
    )
    notes: list[str] = Field(
        default_factory=list,
        description=(
            "Safe-token notes from RECONCILIATION_NOTE_SAFE_FIELDS allow-list only."
        ),
    )

    def sorted_copy(self) -> "ReconciliationNote":
        """Return a copy with `fields_dropped`/`fields_derived`/`notes` sorted."""
        return self.model_copy(
            update={
                "fields_dropped": sorted(self.fields_dropped),
                "fields_derived": sorted(self.fields_derived),
                "notes": sorted(self.notes),
            }
        )
