"""
M7 Schema Translators — Public API.

Pure-library pairwise translators between vendor shapes and M3 canonical types.

Phase 2 Lighthouse Scope: 4 vendors (Salesforce FSC, Orion, eMoney, Schwab)
  × 8 canonical types = 11 translator pairs.

M7 is a LIBRARY. No FastAPI, no HTTP, no network, no file I/O, no credentials,
no logging. M7 imports only from stdlib, pydantic, m3_schema_registry, and
(future) enum-only subset of m5_config_loader.

Usage:

    from m7_schema_translators import (
        translate_to_canonical,
        translate_from_canonical,
        TRANSLATOR_REGISTRY,
        TranslationError,
    )

    canonical, note = translate_to_canonical(
        "salesforce_fsc", "Client", vendor_payload
    )

See `.kiro/specs/m7-schema-translators.md` for the full contract.
"""

from __future__ import annotations

from types import MappingProxyType

from m3_schema_registry import CANONICAL_TYPES, SourceSystem
from pydantic import BaseModel

from m7_schema_translators.errors import (
    VALID_REASON_CODES,
    CostBasisUnmappable,
    MissingRequiredField,
    RoundTripDivergence,
    TranslationError,
    TypeCoercionError,
    UnknownEnumValue,
    UnregisteredTranslator,
    VendorSchemaVersionMismatch,
)
from m7_schema_translators.shared.dispatcher import TranslatorPair
from m7_schema_translators.shared.reconciliation_note import (
    CostBasisSource,
    ReconciliationNote,
)

# EAGER translator imports — fail-closed at package import (AC13.7).
from m7_schema_translators.salesforce_fsc.client import (
    SCHEMA_VERSION as _SF_CLIENT_V,
    VENDOR_API_VERSION as _SF_CLIENT_API,
    from_canonical_client as _sf_client_rev,
    to_canonical_client as _sf_client_fwd,
)
from m7_schema_translators.salesforce_fsc.goal import (
    SCHEMA_VERSION as _SF_GOAL_V,
    VENDOR_API_VERSION as _SF_GOAL_API,
    from_canonical_goal as _sf_goal_rev,
    to_canonical_goal as _sf_goal_fwd,
)
from m7_schema_translators.salesforce_fsc.household import (
    SCHEMA_VERSION as _SF_HH_V,
    VENDOR_API_VERSION as _SF_HH_API,
    from_canonical_household as _sf_hh_rev,
    to_canonical_household as _sf_hh_fwd,
)
from m7_schema_translators.orion.holding import (
    SCHEMA_VERSION as _OR_HOLD_V,
    VENDOR_API_VERSION as _OR_HOLD_API,
    from_canonical_holding as _or_hold_rev,
    to_canonical_holding as _or_hold_fwd,
)
from m7_schema_translators.orion.household import (
    SCHEMA_VERSION as _OR_HH_V,
    VENDOR_API_VERSION as _OR_HH_API,
    from_canonical_household as _or_hh_rev,
    to_canonical_household as _or_hh_fwd,
)
from m7_schema_translators.orion.taxlot import (
    SCHEMA_VERSION as _OR_TL_V,
    VENDOR_API_VERSION as _OR_TL_API,
    from_canonical_taxlot as _or_tl_rev,
    to_canonical_taxlot as _or_tl_fwd,
)
from m7_schema_translators.orion.transaction import (
    SCHEMA_VERSION as _OR_TX_V,
    VENDOR_API_VERSION as _OR_TX_API,
    from_canonical_transaction as _or_tx_rev,
    to_canonical_transaction as _or_tx_fwd,
)
from m7_schema_translators.emoney.plan_summary import (
    SCHEMA_VERSION as _EM_PS_V,
    VENDOR_API_VERSION as _EM_PS_API,
    from_canonical_plan_summary as _em_ps_rev,
    to_canonical_plan_summary as _em_ps_fwd,
)
from m7_schema_translators.schwab.holding import (
    SCHEMA_VERSION as _SC_HOLD_V,
    VENDOR_API_VERSION as _SC_HOLD_API,
    from_canonical_holding as _sc_hold_rev,
    to_canonical_holding as _sc_hold_fwd,
)
from m7_schema_translators.schwab.household import (
    SCHEMA_VERSION as _SC_HH_V,
    VENDOR_API_VERSION as _SC_HH_API,
    from_canonical_household as _sc_hh_rev,
    to_canonical_household as _sc_hh_fwd,
)
from m7_schema_translators.schwab.taxlot import (
    SCHEMA_VERSION as _SC_TL_V,
    VENDOR_API_VERSION as _SC_TL_API,
    from_canonical_taxlot as _sc_tl_rev,
    to_canonical_taxlot as _sc_tl_fwd,
)
from m7_schema_translators.household_multi import (
    to_canonical_household_multi,
)

# Remediation M9 (adapter-agent, 2026 Q2): Bloomberg / ICE Data / Smarsh translators.
from m7_schema_translators.bloomberg.security_profile import (
    SCHEMA_VERSION as _BB_SEC_V,
    VENDOR_API_VERSION as _BB_SEC_API,
    from_canonical_security_profile as _bb_sec_rev,
    to_canonical_security_profile as _bb_sec_fwd,
)
from m7_schema_translators.bloomberg.quote import (
    SCHEMA_VERSION as _BB_Q_V,
    VENDOR_API_VERSION as _BB_Q_API,
    from_canonical_quote as _bb_q_rev,
    to_canonical_quote as _bb_q_fwd,
)
from m7_schema_translators.ice_data.security_profile import (
    SCHEMA_VERSION as _ICE_SEC_V,
    VENDOR_API_VERSION as _ICE_SEC_API,
    from_canonical_security_profile as _ice_sec_rev,
    to_canonical_security_profile as _ice_sec_fwd,
)
from m7_schema_translators.ice_data.quote import (
    SCHEMA_VERSION as _ICE_Q_V,
    VENDOR_API_VERSION as _ICE_Q_API,
    from_canonical_quote as _ice_q_rev,
    to_canonical_quote as _ice_q_fwd,
)
from m7_schema_translators.smarsh.interaction_summary import (
    SCHEMA_VERSION as _SM_IS_V,
    VENDOR_API_VERSION as _SM_IS_API,
    from_canonical_interaction_summary as _sm_is_rev,
    to_canonical_interaction_summary as _sm_is_fwd,
)


SCHEMA_VERSION: str = "0.1.0"


_REGISTRY_RAW: dict[tuple[str, str], TranslatorPair] = {
    ("salesforce_fsc", "Client"): TranslatorPair(
        to_canonical=_sf_client_fwd,
        from_canonical=_sf_client_rev,
        schema_version=_SF_CLIENT_V,
        vendor_api_version=_SF_CLIENT_API,
        module_path="m7_schema_translators.salesforce_fsc.client",
    ),
    ("salesforce_fsc", "Household"): TranslatorPair(
        to_canonical=_sf_hh_fwd,
        from_canonical=_sf_hh_rev,
        schema_version=_SF_HH_V,
        vendor_api_version=_SF_HH_API,
        module_path="m7_schema_translators.salesforce_fsc.household",
    ),
    ("salesforce_fsc", "Goal"): TranslatorPair(
        to_canonical=_sf_goal_fwd,
        from_canonical=_sf_goal_rev,
        schema_version=_SF_GOAL_V,
        vendor_api_version=_SF_GOAL_API,
        module_path="m7_schema_translators.salesforce_fsc.goal",
    ),
    ("orion", "Holding"): TranslatorPair(
        to_canonical=_or_hold_fwd,
        from_canonical=_or_hold_rev,
        schema_version=_OR_HOLD_V,
        vendor_api_version=_OR_HOLD_API,
        module_path="m7_schema_translators.orion.holding",
    ),
    ("orion", "Transaction"): TranslatorPair(
        to_canonical=_or_tx_fwd,
        from_canonical=_or_tx_rev,
        schema_version=_OR_TX_V,
        vendor_api_version=_OR_TX_API,
        module_path="m7_schema_translators.orion.transaction",
    ),
    ("orion", "Household"): TranslatorPair(
        to_canonical=_or_hh_fwd,
        from_canonical=_or_hh_rev,
        schema_version=_OR_HH_V,
        vendor_api_version=_OR_HH_API,
        module_path="m7_schema_translators.orion.household",
    ),
    ("orion", "TaxLot"): TranslatorPair(
        to_canonical=_or_tl_fwd,
        from_canonical=_or_tl_rev,
        schema_version=_OR_TL_V,
        vendor_api_version=_OR_TL_API,
        module_path="m7_schema_translators.orion.taxlot",
    ),
    ("emoney", "PlanSummary"): TranslatorPair(
        to_canonical=_em_ps_fwd,
        from_canonical=_em_ps_rev,
        schema_version=_EM_PS_V,
        vendor_api_version=_EM_PS_API,
        module_path="m7_schema_translators.emoney.plan_summary",
    ),
    ("schwab", "Holding"): TranslatorPair(
        to_canonical=_sc_hold_fwd,
        from_canonical=_sc_hold_rev,
        schema_version=_SC_HOLD_V,
        vendor_api_version=_SC_HOLD_API,
        module_path="m7_schema_translators.schwab.holding",
    ),
    ("schwab", "TaxLot"): TranslatorPair(
        to_canonical=_sc_tl_fwd,
        from_canonical=_sc_tl_rev,
        schema_version=_SC_TL_V,
        vendor_api_version=_SC_TL_API,
        module_path="m7_schema_translators.schwab.taxlot",
    ),
    ("schwab", "Household"): TranslatorPair(
        to_canonical=_sc_hh_fwd,
        from_canonical=_sc_hh_rev,
        schema_version=_SC_HH_V,
        vendor_api_version=_SC_HH_API,
        module_path="m7_schema_translators.schwab.household",
    ),
    # Remediation M9 (adapter-agent 2026 Q2): Bloomberg / ICE Data / Smarsh.
    ("bloomberg", "SecurityProfile"): TranslatorPair(
        to_canonical=_bb_sec_fwd,
        from_canonical=_bb_sec_rev,
        schema_version=_BB_SEC_V,
        vendor_api_version=_BB_SEC_API,
        module_path="m7_schema_translators.bloomberg.security_profile",
    ),
    ("bloomberg", "Quote"): TranslatorPair(
        to_canonical=_bb_q_fwd,
        from_canonical=_bb_q_rev,
        schema_version=_BB_Q_V,
        vendor_api_version=_BB_Q_API,
        module_path="m7_schema_translators.bloomberg.quote",
    ),
    ("ice_data", "SecurityProfile"): TranslatorPair(
        to_canonical=_ice_sec_fwd,
        from_canonical=_ice_sec_rev,
        schema_version=_ICE_SEC_V,
        vendor_api_version=_ICE_SEC_API,
        module_path="m7_schema_translators.ice_data.security_profile",
    ),
    ("ice_data", "Quote"): TranslatorPair(
        to_canonical=_ice_q_fwd,
        from_canonical=_ice_q_rev,
        schema_version=_ICE_Q_V,
        vendor_api_version=_ICE_Q_API,
        module_path="m7_schema_translators.ice_data.quote",
    ),
    ("smarsh", "InteractionSummary"): TranslatorPair(
        to_canonical=_sm_is_fwd,
        from_canonical=_sm_is_rev,
        schema_version=_SM_IS_V,
        vendor_api_version=_SM_IS_API,
        module_path="m7_schema_translators.smarsh.interaction_summary",
    ),
}

TRANSLATOR_REGISTRY: MappingProxyType[tuple[str, str], TranslatorPair] = (
    MappingProxyType(_REGISTRY_RAW)
)


def _validate_pair(source_system: str, canonical_type: str) -> tuple[str, str]:
    """Validate (source_system, canonical_type). Raise `UnregisteredTranslator`."""
    valid_sources = {s.value for s in SourceSystem}
    valid_types = set(CANONICAL_TYPES.keys())
    if source_system not in valid_sources or canonical_type not in valid_types:
        raise UnregisteredTranslator(
            reason_code="unregistered_translator",
            vendor=source_system,
            canonical_type=canonical_type,
            field_path="",
            details={
                "valid_source_systems": sorted(
                    {k[0] for k in TRANSLATOR_REGISTRY}
                ),
                "valid_canonical_types": sorted(
                    {k[1] for k in TRANSLATOR_REGISTRY}
                ),
            },
        )
    key = (source_system, canonical_type)
    if key not in TRANSLATOR_REGISTRY:
        raise UnregisteredTranslator(
            reason_code="unregistered_translator",
            vendor=source_system,
            canonical_type=canonical_type,
            field_path="",
            details={
                "valid_source_systems": sorted(
                    {k[0] for k in TRANSLATOR_REGISTRY}
                ),
                "valid_canonical_types": sorted(
                    {k[1] for k in TRANSLATOR_REGISTRY}
                ),
            },
        )
    return key


def translate_to_canonical(
    source_system: str, canonical_type: str, vendor_payload: dict
) -> tuple[BaseModel, ReconciliationNote]:
    """Dispatch to the registered `to_canonical_*`. Explicit parameters."""
    key = _validate_pair(source_system, canonical_type)
    return TRANSLATOR_REGISTRY[key].to_canonical(vendor_payload)


def translate_from_canonical(
    source_system: str, canonical_type: str, canonical: BaseModel
) -> tuple[BaseModel | None, ReconciliationNote]:
    """Dispatch to the registered `from_canonical_*`."""
    key = _validate_pair(source_system, canonical_type)
    return TRANSLATOR_REGISTRY[key].from_canonical(canonical)


__all__ = [
    "TRANSLATOR_REGISTRY",
    "translate_to_canonical",
    "translate_from_canonical",
    "to_canonical_household_multi",
    "TranslationError",
    "UnknownEnumValue",
    "MissingRequiredField",
    "TypeCoercionError",
    "CostBasisUnmappable",
    "VendorSchemaVersionMismatch",
    "RoundTripDivergence",
    "UnregisteredTranslator",
    "ReconciliationNote",
    "CostBasisSource",
    "TranslatorPair",
    "SCHEMA_VERSION",
    "VALID_REASON_CODES",
]
