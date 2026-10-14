"""
OPA policy client for M2/M4.

Calls OPA REST API for authority (M2) and MNPI filtering (M4).
FAIL-CLOSED: if OPA is unreachable, return DENY. No exceptions.

Includes in-memory fallback evaluator for dev/test that mirrors
the Rego logic locally — no OPA server required for unit tests.

Zero credentials in code — OPA URL from environment only.
"""

from __future__ import annotations

import copy
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from .models import (
    AuthorityDecision,
    FieldFilterEntry,
    MnpiFilterInput,
    MnpiFilterOutput,
    PolicyInput,
    PolicyOutput,
)

logger = logging.getLogger(__name__)

# OPA server URL — from environment, never hardcoded
OPA_URL = os.environ.get("OPA_URL", "http://localhost:8181")
OPA_TIMEOUT_SECONDS = float(os.environ.get("OPA_TIMEOUT_SECONDS", "2.0"))

# ── PII fields that are ALWAYS stripped for non-admin roles ─────
PII_FIELDS = frozenset({"ssn", "dob", "tax_id", "email", "phone"})



# ── Fail-closed DENY response factories ─────────────────────────


def _deny_authority(reason: str) -> PolicyOutput:
    """Produce a DENY PolicyOutput — used for fail-closed defaults."""
    return PolicyOutput(
        decision=AuthorityDecision.DENY,
        reason=reason,
        rule_applied="authority/main.rego:default_deny",
        wsp_section="1.0",
    )


def _deny_mnpi(data_payload: dict[str, Any]) -> MnpiFilterOutput:
    """Produce a fully-stripped MnpiFilterOutput — fail-closed default."""
    return MnpiFilterOutput(
        filtered_payload={},
        fields_removed=list(data_payload.keys()),
        filter_log=[
            FieldFilterEntry(
                field_path=k, mnpi_category="fail_closed"
            )
            for k in data_payload
        ],
        rule_applied="mnpi/main.rego:default_deny",
        wsp_section="3.0",
    )


# ── OPA REST client ─────────────────────────────────────────────


async def _query_opa(path: str, input_data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Query OPA REST API. Returns parsed result or None on failure.
    Fail-closed: any error returns None, caller must DENY.
    """
    url = f"{OPA_URL}/v1/data/{path}"
    try:
        async with httpx.AsyncClient(timeout=OPA_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json={"input": input_data})
            resp.raise_for_status()
            body = resp.json()
            return body.get("result")
    except httpx.ConnectError:
        logger.error("OPA unreachable at %s — DENY (fail-closed)", url)
        return None
    except httpx.TimeoutException:
        logger.error("OPA timeout at %s — DENY (fail-closed)", url)
        return None
    except Exception:
        logger.exception("OPA query failed at %s — DENY (fail-closed)", url)
        return None


async def check_opa_health() -> bool:
    """Check if OPA is reachable."""
    try:
        async with httpx.AsyncClient(timeout=OPA_TIMEOUT_SECONDS) as client:
            resp = await client.get(f"{OPA_URL}/health")
            return resp.status_code == 200
    except Exception:
        return False


# ── M2: Authority evaluation ─────────────────────────────────────


async def evaluate_authority(policy_input: PolicyInput) -> PolicyOutput:
    """
    Evaluate authority policy via OPA.
    FAIL-CLOSED: if OPA unreachable, return DENY.
    """
    opa_input = {
        "identity": {
            "actor_type": policy_input.identity.actor_type,
            "archetype": policy_input.identity.archetype.value,
            "role": policy_input.identity.role.value,
            "firm_id": policy_input.identity.firm_id,
            "jurisdiction": policy_input.identity.jurisdiction,
            "authority_scope": policy_input.identity.authority_scope,
            "authority_excludes": policy_input.identity.authority_excludes,
            "client_scope": policy_input.identity.client_scope,
            "pod_id": policy_input.identity.pod_id,
        },
        "action": policy_input.action,
        "target_type": policy_input.target_type,
        "target_id": policy_input.target_id,
        "context": policy_input.context,
    }

    result = await _query_opa("authority/main", opa_input)

    if result is None:
        return _deny_authority("OPA unreachable — fail-closed DENY")

    # OPA returns the check_authority result object
    decision_str = result.get("decision", "DENY")
    return PolicyOutput(
        decision=AuthorityDecision(decision_str),
        reason=result.get("reason", "No reason provided"),
        rule_applied=result.get("rule", "authority/main.rego:check_authority"),
        wsp_section=result.get("wsp_section", "1.0"),
        details=result.get("details"),
    )


# ── M4: MNPI filter evaluation ──────────────────────────────────


async def evaluate_mnpi_filter(filter_input: MnpiFilterInput) -> MnpiFilterOutput:
    """
    Evaluate MNPI filtering policy via OPA.
    FAIL-CLOSED: if OPA unreachable, strip ALL fields.
    """
    opa_input = {
        "archetype": filter_input.archetype.value,
        "role": filter_input.role.value,
        "jurisdiction": filter_input.jurisdiction,
        "client_scope": filter_input.client_scope,
        "pod_id": filter_input.pod_id,
        "target_client_id": filter_input.target_client_id,
        "target_pod_id": filter_input.target_pod_id,
        "data_fields": list(filter_input.data_payload.keys()),
    }

    result = await _query_opa("mnpi/main", opa_input)

    if result is None:
        return _deny_mnpi(filter_input.data_payload)

    # OPA returns list of fields to strip
    fields_to_strip = set(result.get("fields_to_strip", []))
    access_denied = result.get("access_denied", False)

    if access_denied:
        return _deny_mnpi(filter_input.data_payload)

    filtered_payload = copy.deepcopy(filter_input.data_payload)
    fields_removed: list[str] = []
    filter_log: list[FieldFilterEntry] = []

    for field_name in fields_to_strip:
        if field_name in filtered_payload:
            fields_removed.append(field_name)
            filter_log.append(
                FieldFilterEntry(
                    field_path=field_name,
                    mnpi_category=result.get("field_categories", {}).get(
                        field_name, "pii"
                    ),
                )
            )
            del filtered_payload[field_name]

    return MnpiFilterOutput(
        filtered_payload=filtered_payload,
        fields_removed=fields_removed,
        filter_log=filter_log,
        rule_applied=result.get("rule", "mnpi/main.rego:filter_fields"),
        wsp_section=result.get("wsp_section", "3.0"),
    )



# ═══════════════════════════════════════════════════════════════════
# IN-MEMORY FALLBACK EVALUATOR (dev/test — mirrors Rego logic)
# ═══════════════════════════════════════════════════════════════════


def evaluate_authority_local(policy_input: PolicyInput) -> PolicyOutput:
    """
    In-memory authority evaluation mirroring opa-bundles/authority/main.rego.
    For dev/test only — production MUST use OPA server.
    Default: DENY (fail-closed).
    """
    identity = policy_input.identity
    action = policy_input.action
    context = policy_input.context

    # ── Rule 1: Check authority_excludes (explicit deny list) ────
    for excluded in identity.authority_excludes:
        if _action_matches(action, excluded):
            return PolicyOutput(
                decision=AuthorityDecision.DENY,
                reason=f"Action '{action}' is explicitly excluded by authority_excludes",
                rule_applied="authority/main.rego:check_excludes",
                wsp_section="2.0",
            )

    # ── Rule 2: Check authority_scope (must be in scope) ─────────
    in_scope = False
    for scope_pattern in identity.authority_scope:
        if _action_matches(action, scope_pattern):
            in_scope = True
            break

    if not in_scope:
        return PolicyOutput(
            decision=AuthorityDecision.DENY,
            reason=f"Action '{action}' is not in authority_scope",
            rule_applied="authority/main.rego:check_authority",
            wsp_section="2.0",
        )

    # ── Rule 3: Client scope enforcement ─────────────────────────
    target_client = context.get("client_id") or policy_input.target_id
    if target_client and identity.client_scope:
        if target_client not in identity.client_scope:
            return PolicyOutput(
                decision=AuthorityDecision.DENY,
                reason=f"Client '{target_client}' is not in actor's client_scope",
                rule_applied="authority/main.rego:check_client_scope",
                wsp_section="2.0",
            )

    # ── Rule 4: Pod isolation (Tier 5 HF) ────────────────────────
    target_pod = context.get("target_pod_id")
    if (
        identity.archetype.value == "tier5_hedge_fund"
        and identity.pod_id
        and target_pod
        and identity.pod_id != target_pod
    ):
        return PolicyOutput(
            decision=AuthorityDecision.DENY,
            reason=f"Pod isolation: actor pod '{identity.pod_id}' cannot access pod '{target_pod}'",
            rule_applied="authority/main.rego:check_pod_isolation",
            wsp_section="2.0",
        )

    # ── Rule 5: Escalation for sensitive actions ─────────────────
    escalation_actions = {"order.submit", "wire.send", "account.close"}
    if action in escalation_actions and identity.actor_type == "agent":
        return PolicyOutput(
            decision=AuthorityDecision.ESCALATE,
            reason=f"Action '{action}' requires human approval for agent actors",
            rule_applied="authority/main.rego:check_escalation",
            wsp_section="5.1",
        )

    # ── ALLOW ────────────────────────────────────────────────────
    return PolicyOutput(
        decision=AuthorityDecision.ALLOW,
        reason=f"Action '{action}' is within authority_scope and not excluded",
        rule_applied="authority/main.rego:check_authority",
        wsp_section="2.0",
    )


def evaluate_mnpi_filter_local(filter_input: MnpiFilterInput) -> MnpiFilterOutput:
    """
    In-memory MNPI filtering mirroring opa-bundles/mnpi/main.rego.
    For dev/test only — production MUST use OPA server.
    Default: strip ALL PII (fail-closed).
    """
    archetype = filter_input.archetype.value
    role = filter_input.role.value
    payload = copy.deepcopy(filter_input.data_payload)
    fields_removed: list[str] = []
    filter_log: list[FieldFilterEntry] = []

    # ── Client scope check (Tier 4: own clients only) ────────────
    if filter_input.client_scope and filter_input.target_client_id:
        if filter_input.target_client_id not in filter_input.client_scope:
            return MnpiFilterOutput(
                filtered_payload={},
                fields_removed=list(filter_input.data_payload.keys()),
                filter_log=[
                    FieldFilterEntry(
                        field_path=k, mnpi_category="access_denied"
                    )
                    for k in filter_input.data_payload
                ],
                rule_applied="mnpi/main.rego:client_scope_denied",
                wsp_section="3.0",
            )

    # ── Pod isolation (Tier 5 HF) ────────────────────────────────
    if (
        archetype == "tier5_hedge_fund"
        and filter_input.pod_id
        and filter_input.target_pod_id
        and filter_input.pod_id != filter_input.target_pod_id
    ):
        cross_pod_fields = {
            k for k in payload
            if k in ("positions", "holdings", "pnl", "nav", "exposure")
        }
        for field_name in cross_pod_fields:
            fields_removed.append(field_name)
            filter_log.append(
                FieldFilterEntry(
                    field_path=field_name, mnpi_category="cross_pod"
                )
            )
            del payload[field_name]

    # ── PII stripping (all non-admin and non-compliance_officer roles) ──
    if role not in ("admin", "compliance_officer"):
        for field_name in list(payload.keys()):
            if field_name in PII_FIELDS:
                fields_removed.append(field_name)
                filter_log.append(
                    FieldFilterEntry(
                        field_path=field_name, mnpi_category="pii"
                    )
                )
                del payload[field_name]

    # ── Tier-specific additional filtering ───────────────────────
    if archetype == "tier1_investment_bank":
        division_fields = {
            k for k in payload
            if k in ("deal_pipeline", "ma_targets", "ipo_calendar")
        }
        for field_name in division_fields:
            if role not in ("compliance_officer", "admin"):
                fields_removed.append(field_name)
                filter_log.append(
                    FieldFilterEntry(
                        field_path=field_name, mnpi_category="chinese_wall"
                    )
                )
                del payload[field_name]

    rule = f"mnpi/main.rego:{archetype}_filter"
    return MnpiFilterOutput(
        filtered_payload=payload,
        fields_removed=fields_removed,
        filter_log=filter_log,
        rule_applied=rule,
        wsp_section="3.0",
    )


def _action_matches(action: str, pattern: str) -> bool:
    """
    Check if an action matches a scope pattern.
    Supports exact match and wildcard prefix: 'client.*' matches 'client.read'.
    """
    if action == pattern:
        return True
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return action.startswith(prefix + ".")
    if pattern == "*":
        return True
    return False
