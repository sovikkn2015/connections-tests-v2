# mnpi/main_test.rego — OPA native tests for M4 MNPI filter rules (BLOCKER 3)
#
# Tests all MNPI filter rules:
#   1. Default PII strip for non-admin roles
#   2. Client scope denial — actor cannot access out-of-scope client
#   3. Tier 5 HF pod isolation — strip cross-pod position data
#   4. Tier 1 IB Chinese wall — strip cross-division data
#   5. Tier 3/4 advisor — strip PII, keep holdings
#   6. Admin/CO full access — no fields stripped
#
# Every rule includes wsp_section annotation (Rule 12).

package mnpi.main_test

import rego.v1

import data.mnpi.main


# ═══════════════════════════════════════════════════════════════════
# TEST: Default PII strip — non-admin, non-CO roles
# ═══════════════════════════════════════════════════════════════════

test_default_pii_strip if {
    result := main.filter_result with input as {
        "archetype": "tier2_asset_manager",
        "role": "analyst",
        "jurisdiction": "US",
        "client_scope": [],
        "pod_id": null,
        "target_client_id": null,
        "target_pod_id": null,
        "data_fields": ["name", "ssn", "dob", "email", "phone", "tax_id", "balance"],
    }
    result.access_denied == false
    # PII fields must be in fields_to_strip
    "ssn" in result.fields_to_strip
    "dob" in result.fields_to_strip
    "email" in result.fields_to_strip
    "phone" in result.fields_to_strip
    "tax_id" in result.fields_to_strip
    # Non-PII fields must NOT be stripped
    not "name" in result.fields_to_strip
    not "balance" in result.fields_to_strip
    result.wsp_section == "3.0"
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Client scope denial
# ═══════════════════════════════════════════════════════════════════

test_client_scope_denial if {
    result := main.filter_result with input as {
        "archetype": "tier4_independent_ria",
        "role": "advisor",
        "jurisdiction": "US",
        "client_scope": ["C-111", "C-222"],
        "pod_id": null,
        "target_client_id": "C-999",
        "target_pod_id": null,
        "data_fields": ["name", "ssn", "balance"],
    }
    result.access_denied == true
    # All fields stripped on access denial
    count(result.fields_to_strip) == 3
    result.wsp_section == "3.0"
}

test_client_scope_allows_own_client if {
    result := main.filter_result with input as {
        "archetype": "tier4_independent_ria",
        "role": "advisor",
        "jurisdiction": "US",
        "client_scope": ["C-111", "C-222"],
        "pod_id": null,
        "target_client_id": "C-111",
        "target_pod_id": null,
        "data_fields": ["name", "ssn", "balance"],
    }
    result.access_denied == false
    # Only PII stripped, not all fields
    "ssn" in result.fields_to_strip
    not "name" in result.fields_to_strip
    not "balance" in result.fields_to_strip
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Tier 5 HF pod isolation — strip cross-pod position data
# ═══════════════════════════════════════════════════════════════════

test_tier5_pod_filter_cross_pod if {
    result := main.filter_result with input as {
        "archetype": "tier5_hedge_fund",
        "role": "portfolio_manager",
        "jurisdiction": "US",
        "client_scope": [],
        "pod_id": "pod-alpha",
        "target_client_id": null,
        "target_pod_id": "pod-beta",
        "data_fields": ["name", "ssn", "positions", "holdings", "pnl", "nav", "exposure"],
    }
    result.access_denied == false
    # PII stripped
    "ssn" in result.fields_to_strip
    # Cross-pod position fields stripped
    "positions" in result.fields_to_strip
    "holdings" in result.fields_to_strip
    "pnl" in result.fields_to_strip
    "nav" in result.fields_to_strip
    "exposure" in result.fields_to_strip
    # Non-PII, non-position fields kept
    not "name" in result.fields_to_strip
    result.field_categories.positions == "cross_pod"
    result.wsp_section == "3.0"
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Tier 1 IB Chinese wall — strip cross-division data
# ═══════════════════════════════════════════════════════════════════

test_tier1_chinese_wall_filter if {
    result := main.filter_result with input as {
        "archetype": "tier1_investment_bank",
        "role": "analyst",
        "jurisdiction": "US",
        "client_scope": [],
        "pod_id": null,
        "target_client_id": null,
        "target_pod_id": null,
        "data_fields": ["name", "ssn", "deal_pipeline", "ma_targets", "ipo_calendar", "balance"],
    }
    result.access_denied == false
    # PII stripped
    "ssn" in result.fields_to_strip
    # Chinese wall fields stripped
    "deal_pipeline" in result.fields_to_strip
    "ma_targets" in result.fields_to_strip
    "ipo_calendar" in result.fields_to_strip
    # Non-sensitive fields kept
    not "name" in result.fields_to_strip
    not "balance" in result.fields_to_strip
    result.field_categories.deal_pipeline == "chinese_wall"
    result.wsp_section == "3.0"
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Tier 3 BD advisor — strip PII, keep full holdings
# ═══════════════════════════════════════════════════════════════════

test_tier3_advisor_filter if {
    result := main.filter_result with input as {
        "archetype": "tier3_broker_dealer",
        "role": "advisor",
        "jurisdiction": "US",
        "client_scope": [],
        "pod_id": null,
        "target_client_id": null,
        "target_pod_id": null,
        "data_fields": ["name", "ssn", "dob", "holdings", "balance"],
    }
    result.access_denied == false
    # PII stripped
    "ssn" in result.fields_to_strip
    "dob" in result.fields_to_strip
    # Holdings and non-PII kept
    not "holdings" in result.fields_to_strip
    not "name" in result.fields_to_strip
    not "balance" in result.fields_to_strip
    result.wsp_section == "3.0"
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Tier 4 RIA advisor — strip PII, own clients only
# ═══════════════════════════════════════════════════════════════════

test_tier4_advisor_filter if {
    result := main.filter_result with input as {
        "archetype": "tier4_independent_ria",
        "role": "advisor",
        "jurisdiction": "US",
        "client_scope": ["C-111"],
        "pod_id": null,
        "target_client_id": "C-111",
        "target_pod_id": null,
        "data_fields": ["name", "ssn", "email", "balance"],
    }
    result.access_denied == false
    # PII stripped
    "ssn" in result.fields_to_strip
    "email" in result.fields_to_strip
    # Non-PII kept
    not "name" in result.fields_to_strip
    not "balance" in result.fields_to_strip
    result.wsp_section == "3.0"
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Admin full access — no fields stripped
# ═══════════════════════════════════════════════════════════════════

test_admin_full_access if {
    result := main.filter_result with input as {
        "archetype": "tier4_independent_ria",
        "role": "admin",
        "jurisdiction": "US",
        "client_scope": [],
        "pod_id": null,
        "target_client_id": null,
        "target_pod_id": null,
        "data_fields": ["name", "ssn", "dob", "email", "phone", "tax_id", "balance"],
    }
    result.access_denied == false
    count(result.fields_to_strip) == 0
    result.wsp_section == "3.0"
}


# ═══════════════════════════════════════════════════════════════════
# TEST: Compliance officer full access — no PII filtering
# ═══════════════════════════════════════════════════════════════════

test_compliance_officer_full_access if {
    result := main.filter_result with input as {
        "archetype": "tier1_investment_bank",
        "role": "compliance_officer",
        "jurisdiction": "US",
        "client_scope": [],
        "pod_id": null,
        "target_client_id": null,
        "target_pod_id": null,
        "data_fields": ["name", "ssn", "deal_pipeline", "ma_targets", "balance"],
    }
    result.access_denied == false
    count(result.fields_to_strip) == 0
    result.wsp_section == "3.0"
}
