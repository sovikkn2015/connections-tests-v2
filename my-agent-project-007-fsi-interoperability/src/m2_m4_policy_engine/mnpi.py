"""
M2/M4 Policy Engine — mnpi.py

M4 MNPI Policy. Field-level filtering and MNPI access gate.

Phase 2 migration (R12):
  mnpi/client/ssn_visibility.v1       -> Rego package mnpi.client.ssn_visibility rule v1
  mnpi/client/dob_visibility.v1       -> Rego package mnpi.client.dob_visibility rule v1
  mnpi/client/tax_id_visibility.v1    -> Rego package mnpi.client.tax_id_visibility rule v1
  mnpi/payment/account_visibility.v1  -> Rego package mnpi.payment.account_visibility rule v1
  mnpi/security/mnpi_check.v1         -> Rego package mnpi.security.mnpi_check rule v1

The 5 rules:
  mnpi/client/ssn_visibility.v1       WSP-MNPI-1.1  filter  Client.ssn_last_four
  mnpi/client/dob_visibility.v1       WSP-MNPI-1.2  filter  Client.date_of_birth
  mnpi/client/tax_id_visibility.v1    WSP-MNPI-1.3  filter  Client.tax_id
  mnpi/payment/account_visibility.v1  WSP-MNPI-2.1  filter  PaymentInstruction.beneficiary.account_number
  mnpi/security/mnpi_check.v1         WSP-MNPI-3.1  access  SecurityProfile.mnpi_flag gate
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from m1_identity import AidClaims, Role
from m3_schema_registry import (
    Beneficiary,
    Client,
    PaymentInstruction,
    SecurityProfile,
)

from m2_m4_policy_engine.decisions import Decision, PolicyDecision


# =============================================================================
# Exceptions
# =============================================================================

class UnsupportedTypeForFilterError(TypeError):
    """Raised by ``filter(..., strict=True)`` when the instance type is
    not in the filter table. In trust-critical paths M6 passes
    strict=True to avoid silent pass-through of unhandled types.
    """


# =============================================================================
# Role predicate (R5.2)
# =============================================================================

#: Phase 1 predicate for "authorized to see MNPI field." Spec's
#: ">= senior_advisor" language is documentation-only — Phase 1 uses
#: strict equality with compliance_officer until M1 adds the
#: senior_advisor role.
MNPI_VISIBILITY_PREDICATE_DOC: str = (
    "Phase 1: role == Role.compliance_officer. "
    "Phase 2: role >= senior_advisor (requires M1 to add that role)."
)


def _is_compliance_officer(role: Role) -> bool:
    """Return True iff the given M1 Role is compliance_officer."""
    return role == Role.compliance_officer


# =============================================================================
# Field-filter rule table
# =============================================================================

# Entry shape: (instance_type, field_path, is_authorized, rule_applied,
#               wsp_section, rule_kind, decision_kinds)
_FIELD_RULES: tuple[tuple, ...] = (
    (
        Client,
        ("ssn_last_four",),
        _is_compliance_officer,
        "mnpi/client/ssn_visibility.v1",
        "WSP-MNPI-1.1",
        "mnpi_filter",
        frozenset(),
    ),
    (
        Client,
        ("date_of_birth",),
        _is_compliance_officer,
        "mnpi/client/dob_visibility.v1",
        "WSP-MNPI-1.2",
        "mnpi_filter",
        frozenset(),
    ),
    (
        Client,
        ("tax_id",),
        _is_compliance_officer,
        "mnpi/client/tax_id_visibility.v1",
        "WSP-MNPI-1.3",
        "mnpi_filter",
        frozenset(),
    ),
    (
        PaymentInstruction,
        ("beneficiary", "account_number"),
        _is_compliance_officer,
        "mnpi/payment/account_visibility.v1",
        "WSP-MNPI-2.1",
        "mnpi_filter",
        frozenset(),
    ),
)

# Access rules (return PolicyDecision, not field filters)
# Shape: (instance_type, rule_applied, wsp_section, rule_kind, decision_kinds)
_ACCESS_RULES: tuple[tuple, ...] = (
    (
        SecurityProfile,
        "mnpi/security/mnpi_check.v1",
        "WSP-MNPI-3.1",
        "mnpi_access",
        frozenset({"ALLOW", "DENY"}),
    ),
)


# =============================================================================
# MnpiPolicy class
# =============================================================================

class MnpiPolicy:
    """M4 MNPI Policy.

    filter(claims, instance) returns a Pydantic model_copy with MNPI
    fields redacted for unauthorized roles. It NEVER mutates the input.

    check_mnpi_access(claims, security) returns a PolicyDecision
    (ALLOW / DENY) for the MNPI access gate.

    Construction verifies Beneficiary.account_number exists in M3
    (fail-fast on M3 drift — spec §0.7, R5.4, AC-R5-18).
    """

    def __init__(self) -> None:
        if "account_number" not in Beneficiary.model_fields:
            raise AttributeError(
                "M3 drift: Beneficiary.account_number field missing. "
                "M4 mnpi/payment/account_visibility.v1 depends on it."
            )
        self._field_rules = _FIELD_RULES
        self._access_rules = _ACCESS_RULES

    # -------------------------------------------------------------------
    # Rule-coverage introspection (used by M6 canonicalize glue -- B1).
    # -------------------------------------------------------------------

    def has_filter_rules(self, instance_type: type) -> bool:
        """Return True iff any field rule targets ``instance_type`` (exact
        or subclass match). Used by M6's Stage-6 canonicalize glue to
        decide whether to hand a newly-canonicalized BaseModel to the
        strict filter or emit a JSON-mode dump.
        """
        for rule_tuple in self._field_rules:
            rule_type = rule_tuple[0]
            if isinstance(instance_type, type) and issubclass(
                instance_type, rule_type
            ):
                return True
        return False

    # -------------------------------------------------------------------
    # filter
    # -------------------------------------------------------------------

    def filter(
        self,
        claims: AidClaims,
        instance: BaseModel,
        *,
        strict: bool = False,
    ) -> BaseModel:
        """Return a filtered Pydantic model with MNPI fields redacted.

        Never mutates ``instance``. Returns a Pydantic ``model_copy``.
        Type-stable: returned instance is the exact same class.

        strict=False (default): unsupported instance types pass through
        unchanged (composable with arbitrary canonical types).
        strict=True: unsupported types raise
        UnsupportedTypeForFilterError. M6 passes strict=True in
        trust-critical paths.
        """
        if not isinstance(instance, BaseModel):
            if strict:
                raise UnsupportedTypeForFilterError(
                    f"filter() strict mode rejects non-BaseModel: "
                    f"{type(instance).__name__}"
                )
            return instance

        matched_any = False
        updates: dict[str, Any] = {}

        for (inst_type, path, is_authorized, _rule_applied,
             _wsp, _kind, _kinds) in self._field_rules:
            if not isinstance(instance, inst_type):
                continue
            matched_any = True
            if is_authorized(claims.role):
                continue  # Authorized — leave field alone.

            if len(path) == 1:
                field_name = path[0]
                updates[field_name] = None
            else:
                # Nested path — currently only
                # (beneficiary, account_number). Compose nested
                # model_copy for the outer field.
                outer = path[0]
                inner = path[1]
                outer_val = getattr(instance, outer, None)
                if outer_val is None:
                    continue  # No-op if nested container absent.
                # If an earlier rule already staged an update for the
                # same outer field, chain through so nested rules on
                # the same container compose.
                base_for_update = updates.get(outer, outer_val)
                updates[outer] = base_for_update.model_copy(
                    update={inner: None}
                )

        if not matched_any and strict:
            raise UnsupportedTypeForFilterError(
                f"filter() strict mode: no filter rules for "
                f"{type(instance).__name__}"
            )
        if not updates:
            return instance
        return instance.model_copy(update=updates)

    # -------------------------------------------------------------------
    # check_mnpi_access
    # -------------------------------------------------------------------

    def check_mnpi_access(
        self,
        claims: AidClaims,
        security: SecurityProfile,
    ) -> PolicyDecision:
        """Return ALLOW/DENY for SecurityProfile MNPI access.

        DENY if ``mnpi_flag`` is True AND role != compliance_officer.
        DENY if ``mnpi_flag`` is None (fail-closed for MNPI).
        ALLOW otherwise.
        """
        if not isinstance(security, SecurityProfile):
            raise TypeError("security must be SecurityProfile")

        flag = security.mnpi_flag
        if flag is None:
            flag = True  # Fail-closed: treat missing as MNPI-present.

        if flag and not _is_compliance_officer(claims.role):
            return PolicyDecision(
                decision=Decision.DENY,
                reason="mnpi_flag_set",
                rule_applied="mnpi/security/mnpi_check.v1",
                wsp_section="WSP-MNPI-3.1",
                details={"role": claims.role.value},
            )
        return PolicyDecision(
            decision=Decision.ALLOW,
            reason="mnpi_access_allowed",
            rule_applied="mnpi/security/mnpi_check.v1",
            wsp_section="WSP-MNPI-3.1",
            details={"role": claims.role.value},
        )

    # -------------------------------------------------------------------
    # Inspection helpers
    # -------------------------------------------------------------------

    def list_rules(self) -> list[tuple[str, str]]:
        """Return (rule_applied, wsp_section) for the 5 M4 rules."""
        out: list[tuple[str, str]] = []
        for (_t, _p, _auth, rule_applied, wsp, _k, _kinds) in self._field_rules:
            out.append((rule_applied, wsp))
        for (_t, rule_applied, wsp, _k, _kinds) in self._access_rules:
            out.append((rule_applied, wsp))
        return out

    def rule_table(self) -> list[dict]:
        """Return structured inventory for WSP-to-YAML mapping.

        Entries carry rule_applied, wsp_section, archetypes (always
        ["ALL"] for M4 Phase 1), actions (always ["ALL"]), rule_kind
        (mnpi_filter | mnpi_access), decision_kinds (sorted), and the
        filter target/field_path for traceability.
        """
        rows: list[dict] = []
        for (inst_type, path, _auth, rule_applied, wsp, kind,
             _kinds) in self._field_rules:
            rows.append(
                {
                    "rule_applied": rule_applied,
                    "wsp_section": wsp,
                    "archetypes": ["ALL"],
                    "actions": ["ALL"],
                    "rule_kind": kind,
                    "decision_kinds": [],
                    "filter_target": inst_type.__name__,
                    "filter_field_path": ".".join(path),
                }
            )
        for (inst_type, rule_applied, wsp, kind, kinds) in self._access_rules:
            rows.append(
                {
                    "rule_applied": rule_applied,
                    "wsp_section": wsp,
                    "archetypes": ["ALL"],
                    "actions": ["ALL"],
                    "rule_kind": kind,
                    "decision_kinds": sorted(kinds),
                    "filter_target": inst_type.__name__,
                    "filter_field_path": "mnpi_flag",
                }
            )
        return rows
