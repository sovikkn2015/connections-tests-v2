# account-type/erisa.rego — ERISA Account-Type Rules (Gap 5)
#
# Prohibited transaction detection (ERISA §406), concentration limits,
# plan investment menu enforcement for ERISA-governed accounts.
#
# Every rule includes wsp_section annotation (steering rule 19).
# OPA/Rego ONLY — no LLM for compliance decisions.

package account_type.erisa

import rego.v1

# ERISA-governed account types
erisa_account_types := {"401k", "403b", "457b", "erisa_pension"}

# ═══════════════════════════════════════════════════════════════════
# DEFAULT: PASS (no ERISA violation detected)
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Default ERISA check
# description: No ERISA violation detected — pass through
# custom:
#   wsp_section: "WSP-9.1"
#   gap: 5
#   severity: "PASS"
default check_erisa := {
    "decision": "PASS",
    "reason": "No ERISA violation detected",
    "rule": "account_type/erisa.rego:default",
    "wsp_section": "WSP-9.1",
}

# ═══════════════════════════════════════════════════════════════════
# RULE 1: Prohibited transaction — party-in-interest (ERISA §406)
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: ERISA prohibited transaction check
# description: Denies transactions with party-in-interest under ERISA §406
# custom:
#   wsp_section: "WSP-9.1"
#   gap: 5
#   severity: "BLOCK"
check_erisa := result if {
    input.account_type in erisa_account_types
    input.counterparty_id != null
    data.party_in_interest_list[input.counterparty_id]
    result := {
        "decision": "DENY",
        "reason": sprintf(
            "Prohibited transaction: %s is a party-in-interest under ERISA §406",
            [input.counterparty_id],
        ),
        "rule": "account_type/erisa.rego:check_prohibited_transaction",
        "wsp_section": "WSP-9.1",
        "account_type": input.account_type,
        "counterparty_id": input.counterparty_id,
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 2: ERISA concentration limit (10% vs standard 15%)
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: ERISA concentration check
# description: Warns when ERISA account exceeds 10% single-position concentration
# custom:
#   wsp_section: "WSP-9.1"
#   gap: 5
#   severity: "WARN"
check_erisa := result if {
    input.account_type in erisa_account_types
    input.proposed_position_pct > 10
    not is_prohibited_transaction
    result := {
        "decision": "WARN",
        "reason": sprintf(
            "ERISA prudent investor: %.1f%% concentration exceeds 10%% guideline",
            [input.proposed_position_pct],
        ),
        "rule": "account_type/erisa.rego:check_erisa_concentration",
        "wsp_section": "WSP-9.1",
        "account_type": input.account_type,
        "proposed_pct": input.proposed_position_pct,
        "limit_pct": 10,
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 3: 401k/403b plan investment menu enforcement
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Plan investment menu check
# description: Denies securities not in the plan's approved investment menu
# custom:
#   wsp_section: "WSP-9.1"
#   gap: 5
#   severity: "BLOCK"
check_erisa := result if {
    input.account_type in {"401k", "403b"}
    input.plan_id != null
    input.security_id != null
    plan_menu := data.plan_investment_menus[input.plan_id]
    not plan_menu[input.security_id]
    not is_prohibited_transaction
    result := {
        "decision": "DENY",
        "reason": sprintf(
            "Security %s not in plan %s approved investment menu",
            [input.security_id, input.plan_id],
        ),
        "rule": "account_type/erisa.rego:check_plan_investment_menu",
        "wsp_section": "WSP-9.1",
        "account_type": input.account_type,
        "security_id": input.security_id,
        "plan_id": input.plan_id,
    }
}

# ═══════════════════════════════════════════════════════════════════
# HELPER: check if prohibited transaction applies
# ═══════════════════════════════════════════════════════════════════

is_prohibited_transaction if {
    input.account_type in erisa_account_types
    input.counterparty_id != null
    data.party_in_interest_list[input.counterparty_id]
}
