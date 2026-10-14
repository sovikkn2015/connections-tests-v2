# account-type/erisa_test.rego — OPA native tests for ERISA rules (Gap 5)
#
# Tests:
#   1. Prohibited transaction — party-in-interest denied
#   2. Prohibited transaction — non-party passes
#   3. Concentration limit — >10% triggers WARN
#   4. Concentration limit — <=10% passes
#   5. Plan investment menu — security not in menu denied
#   6. Default pass — non-ERISA account
#
# Every rule includes wsp_section annotation (steering rule 19).

package account_type.erisa_test

import rego.v1

import data.account_type.erisa

# ═══════════════════════════════════════════════════════════════════
# TEST: Prohibited transaction — party-in-interest DENY
# ═══════════════════════════════════════════════════════════════════

test_prohibited_transaction_denied if {
    result := erisa.check_erisa with input as {
        "account_type": "401k",
        "counterparty_id": "CP-INSIDER-001",
        "proposed_position_pct": 5,
        "plan_id": null,
        "security_id": null,
    } with data.party_in_interest_list as {"CP-INSIDER-001": true}
    result.decision == "DENY"
    contains(result.reason, "party-in-interest")
    result.wsp_section == "WSP-9.1"
}

test_prohibited_transaction_non_party_passes if {
    result := erisa.check_erisa with input as {
        "account_type": "401k",
        "counterparty_id": "CP-NORMAL-001",
        "proposed_position_pct": 5,
        "plan_id": null,
        "security_id": null,
    } with data.party_in_interest_list as {"CP-INSIDER-001": true}
    result.decision == "PASS"
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Concentration limit — ERISA 10% threshold
# ═══════════════════════════════════════════════════════════════════

test_concentration_above_10_warns if {
    result := erisa.check_erisa with input as {
        "account_type": "403b",
        "counterparty_id": null,
        "proposed_position_pct": 12.5,
        "plan_id": null,
        "security_id": null,
    }
    result.decision == "WARN"
    contains(result.reason, "concentration")
    result.wsp_section == "WSP-9.1"
}

test_concentration_at_10_passes if {
    result := erisa.check_erisa with input as {
        "account_type": "403b",
        "counterparty_id": null,
        "proposed_position_pct": 10,
        "plan_id": null,
        "security_id": null,
    }
    result.decision == "PASS"
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Plan investment menu — security not in menu DENY
# ═══════════════════════════════════════════════════════════════════

test_plan_menu_security_not_in_menu_denied if {
    result := erisa.check_erisa with input as {
        "account_type": "401k",
        "counterparty_id": null,
        "proposed_position_pct": 5,
        "plan_id": "PLAN-001",
        "security_id": "SEC-UNAPPROVED",
    } with data.plan_investment_menus as {"PLAN-001": {"SEC-APPROVED-A": true, "SEC-APPROVED-B": true}}
    result.decision == "DENY"
    contains(result.reason, "not in plan")
    result.wsp_section == "WSP-9.1"
}

test_plan_menu_security_in_menu_passes if {
    result := erisa.check_erisa with input as {
        "account_type": "401k",
        "counterparty_id": null,
        "proposed_position_pct": 5,
        "plan_id": "PLAN-001",
        "security_id": "SEC-APPROVED-A",
    } with data.plan_investment_menus as {"PLAN-001": {"SEC-APPROVED-A": true}}
    result.decision == "PASS"
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Default pass — non-ERISA account type
# ═══════════════════════════════════════════════════════════════════

test_non_erisa_account_passes if {
    result := erisa.check_erisa with input as {
        "account_type": "individual_brokerage",
        "counterparty_id": null,
        "proposed_position_pct": 50,
        "plan_id": null,
        "security_id": null,
    }
    result.decision == "PASS"
}
