"""M6 → M7 canonicalization middleware.

Rule 33 (no cross-module imports) is preserved at the adapter layer: adapters
stay vendor-pure. Canonicalization happens at the M6 gateway's translate stage
(Stage 6 of ``TrustAwareGateway.call``), AFTER the vendor adapter returns its
raw payload and BEFORE the M4 MNPI response filter.

This module imports ``m7_schema_translators`` — that is the ONE module import
allowed here, because M6 is the trust-pipeline owner and M7 is a pure library.
Neither M11 nor M13 imports M7; they return raw vendor shapes and trust M6
to canonicalize.

Contract:

* ``Canonicalizer.translate(vendor, tool_name, raw_payload)`` returns the
  canonical M3 model when ``(vendor, tool_name)`` has a registered
  translator.
* When no translator is registered for ``(vendor, tool_name)`` the raw
  payload passes through unchanged. Not every tool has a canonical M3
  shape — e.g. Smarsh search returns unstructured transcripts.
* When a translator IS registered but the vendor payload is the wrong shape,
  ``translate`` re-raises the :class:`m7_schema_translators.TranslationError`.
  The caller (M6 gateway) decides whether to map that into a ``vendor_error``
  ``GatewayError`` or let it fail-closed.

Registration data structure:

* ``DISPATCH`` is a module-level ``MappingProxyType`` keyed by
  ``(vendor, tool_name)`` pointing at ``(source_system, canonical_type)``
  which the Canonicalizer then routes into ``translate_to_canonical``.
* Tool names use the canonical namespace convention — e.g. the Orion holdings
  tool is named ``orion.fetch_holdings``. Vendors without dedicated tools
  (Bloomberg, ICE) use their declared namespaces too: ``bloomberg.reference_data``,
  ``ice_data.get_security_profile``.

See ``.kiro/specs/remediation-adapter-fixes.md`` §B1 for background.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Optional

from m7_schema_translators import (
    ReconciliationNote,
    TranslationError,
    translate_to_canonical,
)


# =============================================================================
# Dispatch table
# =============================================================================

# (vendor, tool_name) -> (source_system, canonical_type)
#
# Keys MUST match:
#   - ``vendor``  : the M6 request's ``mcp_server`` slug (matches
#                   ``m11_rest_adapters/<vendor>/`` + ``m11_<family>_adapters/``).
#   - ``tool_name``: the MCP tool name exposed by the adapter.
#
# Values MUST match keys in ``m7_schema_translators.TRANSLATOR_REGISTRY``.
#
# NOT EVERY TOOL IS HERE. By design, tools that return free-form text
# (search transcripts, agent-generated summaries, etc.) have no canonical
# shape and pass through unchanged.
_DISPATCH_RAW: dict[tuple[str, str], tuple[str, str]] = {
    # ---- Salesforce FSC ----
    ("salesforce_fsc", "sfdc.fetch_client"): ("salesforce_fsc", "Client"),
    ("salesforce_fsc", "sfdc.fetch_household"): ("salesforce_fsc", "Household"),
    ("salesforce_fsc", "sfdc.fetch_goal"): ("salesforce_fsc", "Goal"),
    # ---- Orion ----
    ("orion", "orion.fetch_holdings"): ("orion", "Holding"),
    ("orion", "orion.fetch_taxlots"): ("orion", "TaxLot"),
    ("orion", "orion.fetch_transactions"): ("orion", "Transaction"),
    ("orion", "orion.fetch_household"): ("orion", "Household"),
    # ---- Schwab ----
    ("schwab", "schwab.fetch_holdings"): ("schwab", "Holding"),
    ("schwab", "schwab.fetch_taxlots"): ("schwab", "TaxLot"),
    ("schwab", "schwab.fetch_household"): ("schwab", "Household"),
    # ---- eMoney ----
    ("emoney", "emoney.fetch_plan_summary"): ("emoney", "PlanSummary"),
    # ---- Bloomberg (M11-BLPAPI) ----
    ("bloomberg", "bloomberg.reference_data"): ("bloomberg", "SecurityProfile"),
    ("bloomberg", "bloomberg.intraday_tick"): ("bloomberg", "Quote"),
    # ---- ICE Data (M11-gRPC) ----
    ("ice_data", "ice_data.get_security_profile"): ("ice_data", "SecurityProfile"),
    ("ice_data", "ice_data.get_quote"): ("ice_data", "Quote"),
    # ---- Smarsh Archive ----
    # `smarsh.search` returns transcripts (unstructured) -- no entry.
    # `smarsh.get_interaction_summary` is the structured one.
    ("smarsh", "smarsh.get_interaction_summary"): ("smarsh", "InteractionSummary"),
    ("smarsh_archive", "smarsh.get_interaction_summary"): ("smarsh", "InteractionSummary"),
}

DISPATCH: MappingProxyType[tuple[str, str], tuple[str, str]] = MappingProxyType(
    _DISPATCH_RAW
)


# =============================================================================
# Result container
# =============================================================================


@dataclass(frozen=True)
class CanonicalizeResult:
    """Canonicalize result. When ``translated`` is False the raw payload
    passes through unchanged and ``note`` is None."""

    payload: Any
    translated: bool
    source_system: Optional[str]
    canonical_type: Optional[str]
    note: Optional[ReconciliationNote]


# =============================================================================
# Canonicalizer
# =============================================================================


class Canonicalizer:
    """Stateless wrapper around the dispatch table.

    Carries the mapping in a constructor so M6 tests can inject a reduced
    dispatch. Production code instantiates the default singleton via
    :func:`default_canonicalizer`.
    """

    def __init__(
        self,
        dispatch: MappingProxyType[tuple[str, str], tuple[str, str]] | None = None,
    ) -> None:
        self._dispatch = dispatch if dispatch is not None else DISPATCH

    def has_translator(self, vendor: str, tool_name: str) -> bool:
        return (vendor, tool_name) in self._dispatch

    def translate(
        self,
        vendor: str,
        tool_name: str,
        raw_payload: Any,
    ) -> CanonicalizeResult:
        """Translate raw adapter output to an M3 canonical model.

        Returns a :class:`CanonicalizeResult`. When no translator is
        registered for ``(vendor, tool_name)`` the call is a pass-through:
        ``payload == raw_payload`` and ``translated is False``.

        Translation failures (:class:`TranslationError`) propagate up; the
        caller decides how to surface them (M6 maps them into
        ``vendor_error``).

        Non-dict ``raw_payload`` values pass through with ``translated=False``
        — this guards the case where the adapter returned a
        ``pydantic.BaseModel`` that already represents a canonical shape, or
        when a stub vendor adapter emitted a primitive for tests. Checking
        dict-shape up-front keeps M7's strict pydantic validation from
        blowing up on non-dict inputs.
        """
        key = (vendor, tool_name)
        pair = self._dispatch.get(key)
        if pair is None:
            return CanonicalizeResult(
                payload=raw_payload,
                translated=False,
                source_system=None,
                canonical_type=None,
                note=None,
            )

        if not isinstance(raw_payload, dict):
            # Pass through — canonical model already, or test stub.
            return CanonicalizeResult(
                payload=raw_payload,
                translated=False,
                source_system=pair[0],
                canonical_type=pair[1],
                note=None,
            )

        source_system, canonical_type = pair
        canonical, note = translate_to_canonical(
            source_system, canonical_type, raw_payload
        )
        return CanonicalizeResult(
            payload=canonical,
            translated=True,
            source_system=source_system,
            canonical_type=canonical_type,
            note=note,
        )


_DEFAULT_INSTANCE: Canonicalizer | None = None


def default_canonicalizer() -> Canonicalizer:
    """Return the module-level default Canonicalizer (lazy-built)."""
    global _DEFAULT_INSTANCE
    if _DEFAULT_INSTANCE is None:
        _DEFAULT_INSTANCE = Canonicalizer()
    return _DEFAULT_INSTANCE


__all__ = [
    "Canonicalizer",
    "CanonicalizeResult",
    "DISPATCH",
    "TranslationError",
    "default_canonicalizer",
]
