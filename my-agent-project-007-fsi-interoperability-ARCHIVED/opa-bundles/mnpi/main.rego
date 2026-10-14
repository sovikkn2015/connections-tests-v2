# mnpi/main.rego — Core M4 MNPI Filtering Rules
#
# Per-field data filtering by archetype, role, and jurisdiction.
# Default: strip ALL PII fields (fail-closed).
#
# Every rule includes wsp_section annotation (steering rule 19).
# OPA/Rego ONLY — no LLM for compliance decisions.
#
# Archetypes:
#   tier3_broker_dealer  — strip PII, keep full holdings
#   tier4_independent_ria — strip PII, own clients only
#   tier5_hedge_fund     — strip cross-pod position data
#   tier1_investment_bank — Chinese wall enforcement across divisions

package mnpi.main

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# PII FIELDS — always stripped for non-admin roles
# ═══════════════════════════════════════════════════════════════════

pii_fields := {"ssn", "dob", "tax_id", "email", "phone"}

# Cross-pod position fields (Tier 5 HF)
position_fields := {"positions", "holdings", "pnl", "nav", "exposure"}

# Chinese wall fields (Tier 1 IB)
chinese_wall_fields := {"deal_pipeline", "ma_targets", "ipo_calendar"}

# ═══════════════════════════════════════════════════════════════════
# DEFAULT: strip all PII (fail-closed)
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Default MNPI filter
# description: Default strips all PII fields — fail-closed
# custom:
#   wsp_section: "3.0"
default filter_result := {
    "fields_to_strip": ["ssn", "dob", "tax_id", "email", "phone"],
    "field_categories": {
        "ssn": "pii", "dob": "pii", "tax_id": "pii",
        "email": "pii", "phone": "pii",
    },
    "access_denied": false,
    "rule": "mnpi/main.rego:default_filter",
    "wsp_section": "3.0",
}

# ═══════════════════════════════════════════════════════════════════
# CLIENT SCOPE DENIAL — actor cannot access this client's data
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Client scope denial
# description: Actor cannot access data for clients outside their scope
# custom:
#   wsp_section: "3.0"
filter_result := result if {
    count(input.client_scope) > 0
    input.target_client_id != null
    not input.target_client_id in input.client_scope
    result := {
        "fields_to_strip": input.data_fields,
        "field_categories": {f: "access_denied" | some f in input.data_fields},
        "access_denied": true,
        "rule": "mnpi/main.rego:client_scope_denied",
        "wsp_section": "3.0",
    }
}

# ═══════════════════════════════════════════════════════════════════
# TIER 5 HF: Pod isolation — strip cross-pod position data
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Tier 5 pod isolation filter
# description: Strip cross-pod position data for hedge fund actors
# custom:
#   wsp_section: "3.0"
filter_result := result if {
    input.archetype == "tier5_hedge_fund"
    input.pod_id != null
    input.target_pod_id != null
    input.pod_id != input.target_pod_id
    not client_scope_denied
    pii_to_strip := {f | some f in input.data_fields; f in pii_fields}
    pod_to_strip := {f | some f in input.data_fields; f in position_fields}
    all_stripped := pii_to_strip | pod_to_strip
    pii_cats := {f: "pii" | some f in pii_to_strip}
    pod_cats := {f: "cross_pod" | some f in pod_to_strip}
    cats := object.union(pii_cats, pod_cats)
    result := {
        "fields_to_strip": sort(all_stripped),
        "field_categories": cats,
        "access_denied": false,
        "rule": "mnpi/main.rego:tier5_pod_filter",
        "wsp_section": "3.0",
    }
}


# ═══════════════════════════════════════════════════════════════════
# TIER 1 IB: Chinese wall — strip cross-division data
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Tier 1 Chinese wall filter
# description: Strip cross-division MNPI for investment bank actors
# custom:
#   wsp_section: "3.0"
filter_result := result if {
    input.archetype == "tier1_investment_bank"
    input.role != "compliance_officer"
    input.role != "admin"
    not client_scope_denied
    pii_to_strip := {f | some f in input.data_fields; f in pii_fields}
    wall_to_strip := {f | some f in input.data_fields; f in chinese_wall_fields}
    all_stripped := pii_to_strip | wall_to_strip
    pii_cats := {f: "pii" | some f in pii_to_strip}
    wall_cats := {f: "chinese_wall" | some f in wall_to_strip}
    cats := object.union(pii_cats, wall_cats)
    result := {
        "fields_to_strip": sort(all_stripped),
        "field_categories": cats,
        "access_denied": false,
        "rule": "mnpi/main.rego:tier1_chinese_wall_filter",
        "wsp_section": "3.0",
    }
}

# ═══════════════════════════════════════════════════════════════════
# TIER 3 BD: Advisor filter — strip PII, keep full holdings
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Tier 3 advisor filter
# description: Strip PII for broker-dealer advisors, keep full holdings
# custom:
#   wsp_section: "3.0"
filter_result := result if {
    input.archetype == "tier3_broker_dealer"
    input.role == "advisor"
    not client_scope_denied
    to_strip := {f | some f in input.data_fields; f in pii_fields}
    cats := {f: "pii" | some f in to_strip}
    result := {
        "fields_to_strip": sort(to_strip),
        "field_categories": cats,
        "access_denied": false,
        "rule": "mnpi/main.rego:tier3_advisor_filter",
        "wsp_section": "3.0",
    }
}

# ═══════════════════════════════════════════════════════════════════
# TIER 4 RIA: Advisor filter — strip PII, own clients only
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Tier 4 advisor filter
# description: Strip PII for RIA advisors, own clients only enforced by client_scope
# custom:
#   wsp_section: "3.0"
filter_result := result if {
    input.archetype == "tier4_independent_ria"
    input.role == "advisor"
    not client_scope_denied
    to_strip := {f | some f in input.data_fields; f in pii_fields}
    cats := {f: "pii" | some f in to_strip}
    result := {
        "fields_to_strip": sort(to_strip),
        "field_categories": cats,
        "access_denied": false,
        "rule": "mnpi/main.rego:tier4_advisor_filter",
        "wsp_section": "3.0",
    }
}

# ═══════════════════════════════════════════════════════════════════
# ADMIN: No filtering (full access)
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Admin full access
# description: Admin role has full access — no fields stripped
# custom:
#   wsp_section: "3.0"
filter_result := result if {
    input.role == "admin"
    result := {
        "fields_to_strip": [],
        "field_categories": {},
        "access_denied": false,
        "rule": "mnpi/main.rego:admin_full_access",
        "wsp_section": "3.0",
    }
}

# ═══════════════════════════════════════════════════════════════════
# COMPLIANCE OFFICER: No PII filtering (needs full view for oversight)
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Compliance officer access
# description: Compliance officers see all fields for oversight duties
# custom:
#   wsp_section: "3.0"
filter_result := result if {
    input.role == "compliance_officer"
    result := {
        "fields_to_strip": [],
        "field_categories": {},
        "access_denied": false,
        "rule": "mnpi/main.rego:compliance_officer_access",
        "wsp_section": "3.0",
    }
}

# ═══════════════════════════════════════════════════════════════════
# HELPER: client scope denial check
# ═══════════════════════════════════════════════════════════════════

client_scope_denied if {
    count(input.client_scope) > 0
    input.target_client_id != null
    not input.target_client_id in input.client_scope
}
