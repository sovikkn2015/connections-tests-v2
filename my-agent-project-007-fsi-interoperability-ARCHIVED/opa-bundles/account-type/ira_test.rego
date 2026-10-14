# account-type/ira_test.rego — OPA native tests for IRA rules (Gap 5)
#
# Tests:
#   1. RMD check — age 73+, Q4, RMD not taken → WARN
#   2. RMD check — age 73+, RMD already taken → PASS
#   3. RMD check — age below 73 → PASS
#   4. Roth 5-year rule — account < 5 years, client < 59.5 → WARN
#   5. Roth 5-year rule — account >= 5 years → PASS
#   6. Default pass — non-IRA account
#
# Every rule includes wsp_section annotation (steering rule 19).

package account_type.ira_test

import rego.v1

import data.account_type.ira

# ═══════════════════════════════════════════════════════════════════
# TEST: RMD check — age 73+, Q4, not yet taken → WARN
# ═══════════════════════════════════════════════════════════════════

test_rmd_warns_age_73_q4_not_taken if {
    result := ira.check_ira with input as {
        "account_type": "traditional_ira",
        "client_age": 75,
        "rmd_taken_this_year": false,
        "current_month": 10,
        "action": "review",
        "proposed_position_pct": 5,
    }
    result.decision == "WARN"
    contains(result.reason, "RMD")
    result.wsp_section == "WSP-9.2"
    result.flag_in_meeting_prep == true
}

test_rmd_passes_when_already_taken if {
    result := ira.check_ira with input as {
        "account_type": "traditional_ira",
        "client_age": 75,
        "rmd_taken_this_year": true,
        "current_month": 11,
        "action": "review",
        "proposed_position_pct": 5,
    }
    result.decision == "PASS"
}

test_rmd_passes_below_age_73 if {
    result := ira.check_ira with input as {
        "account_type": "traditional_ira",
        "client_age": 65,
        "rmd_taken_this_year": false,
        "current_month": 11,
        "action": "review",
        "proposed_position_pct": 5,
    }
    result.decision == "PASS"
}

test_rmd_passes_before_q4 if {
    result := ira.check_ira with input as {
        "account_type": "sep_ira",
        "client_age": 74,
        "rmd_taken_this_year": false,
        "current_month": 6,
        "action": "review",
        "proposed_position_pct": 5,
    }
    result.decision == "PASS"
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Roth 5-year rule — early withdrawal warning
# ═══════════════════════════════════════════════════════════════════

test_roth_5year_warns_early_withdrawal if {
    result := ira.check_ira with input as {
        "account_type": "roth_ira",
        "action": "withdraw",
        "roth_account_age_years": 3,
        "client_age": 45,
        "proposed_position_pct": 5,
    }
    result.decision == "WARN"
    contains(result.reason, "Roth")
    contains(result.reason, "penalties")
    result.wsp_section == "WSP-9.2"
}

test_roth_5year_passes_mature_account if {
    result := ira.check_ira with input as {
        "account_type": "roth_ira",
        "action": "withdraw",
        "roth_account_age_years": 6,
        "client_age": 45,
        "proposed_position_pct": 5,
    }
    result.decision == "PASS"
}

test_roth_5year_passes_over_59_5 if {
    result := ira.check_ira with input as {
        "account_type": "roth_ira",
        "action": "withdraw",
        "roth_account_age_years": 3,
        "client_age": 62,
        "proposed_position_pct": 5,
    }
    result.decision == "PASS"
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Default pass — non-IRA account type
# ═══════════════════════════════════════════════════════════════════

test_non_ira_account_passes if {
    result := ira.check_ira with input as {
        "account_type": "individual_brokerage",
        "client_age": 80,
        "rmd_taken_this_year": false,
        "current_month": 12,
        "action": "review",
        "proposed_position_pct": 5,
    }
    result.decision == "PASS"
}
