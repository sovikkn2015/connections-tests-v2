# account-type/ira.rego — IRA Account-Type Rules (Gap 5)
#
# RMD checks, Roth 5-year rule, contribution limit awareness
# for Traditional IRA, Roth IRA, SEP IRA, SIMPLE IRA.
#
# Every rule includes wsp_section annotation (steering rule 19).
# OPA/Rego ONLY — no LLM for compliance decisions.

package account_type.ira

import rego.v1

# IRA account types subject to RMD
rmd_account_types := {"traditional_ira", "sep_ira", "simple_ira", "401k", "403b", "457b"}

# ═══════════════════════════════════════════════════════════════════
# DEFAULT: PASS
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Default IRA check
# description: No IRA-specific violation detected
# custom:
#   wsp_section: "WSP-9.2"
#   gap: 5
#   severity: "PASS"
default check_ira := {
    "decision": "PASS",
    "reason": "No IRA-specific violation detected",
    "rule": "account_type/ira.rego:default",
    "wsp_section": "WSP-9.2",
}

# ═══════════════════════════════════════════════════════════════════
# RULE 1: RMD check — client age 73+ and RMD not yet taken
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Required Minimum Distribution check
# description: Warns if RMD not yet taken for age 73+ in Q4
# custom:
#   wsp_section: "WSP-9.2"
#   gap: 5
#   severity: "WARN"
check_ira := result if {
    input.account_type in rmd_account_types
    input.client_age >= 73
    input.rmd_taken_this_year == false
    input.current_month >= 10
    result := {
        "decision": "WARN",
        "reason": sprintf(
            "RMD not yet taken for %s — client age %d, due by December 31",
            [input.account_type, input.client_age],
        ),
        "rule": "account_type/ira.rego:check_rmd_status",
        "wsp_section": "WSP-9.2",
        "account_type": input.account_type,
        "client_age": input.client_age,
        "flag_in_meeting_prep": true,
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 2: Roth IRA 5-year rule
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Roth IRA 5-year rule check
# description: Warns on Roth withdrawal if account < 5 years and client under 59.5
# custom:
#   wsp_section: "WSP-9.2"
#   gap: 5
#   severity: "WARN"
check_ira := result if {
    input.account_type == "roth_ira"
    input.action == "withdraw"
    input.roth_account_age_years < 5
    input.client_age < 59.5
    result := {
        "decision": "WARN",
        "reason": sprintf(
            "Roth withdrawal may incur penalties — account age %d years (< 5) and client age %.1f (< 59.5)",
            [input.roth_account_age_years, input.client_age],
        ),
        "rule": "account_type/ira.rego:check_roth_5year",
        "wsp_section": "WSP-9.2",
        "account_type": input.account_type,
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 3: IRA concentration limit (standard 15%)
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: IRA concentration check
# description: Warns when IRA exceeds 15% single-position concentration
# custom:
#   wsp_section: "WSP-9.2"
#   gap: 5
#   severity: "WARN"
check_ira := result if {
    input.account_type in {"traditional_ira", "roth_ira", "sep_ira", "simple_ira"}
    input.proposed_position_pct > 15
    result := {
        "decision": "WARN",
        "reason": sprintf(
            "IRA concentration: %.1f%% exceeds 15%% guideline for %s",
            [input.proposed_position_pct, input.account_type],
        ),
        "rule": "account_type/ira.rego:check_ira_concentration",
        "wsp_section": "WSP-9.2",
        "account_type": input.account_type,
        "proposed_pct": input.proposed_position_pct,
        "limit_pct": 15,
    }
}
