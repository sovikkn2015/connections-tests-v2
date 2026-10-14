# account-type/trust.rego — Trust & Custodial Account Rules (Gap 5)
#
# Trust duty of impartiality, UGMA/UTMA restrictions,
# estate account constraints.
#
# Every rule includes wsp_section annotation (steering rule 19).
# OPA/Rego ONLY — no LLM for compliance decisions.

package account_type.trust

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# DEFAULT: PASS
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Default trust check
# description: No trust-specific violation detected
# custom:
#   wsp_section: "WSP-9.3"
#   gap: 5
#   severity: "PASS"
default check_trust := {
    "decision": "PASS",
    "reason": "No trust-specific violation detected",
    "rule": "account_type/trust.rego:default",
    "wsp_section": "WSP-9.3",
}

# ═══════════════════════════════════════════════════════════════════
# RULE 1: Trust duty of impartiality — income vs. remainder
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Trust impartiality check
# description: Warns when trust portfolio yield is low and buying non-income security
# custom:
#   wsp_section: "WSP-9.3"
#   gap: 5
#   severity: "WARN"
check_trust := result if {
    input.account_type in {"trust_revocable", "trust_irrevocable"}
    input.trust_has_income_beneficiary == true
    input.trust_has_remainder_beneficiary == true
    input.portfolio_income_yield < 0.02
    input.security_yield == 0
    result := {
        "decision": "WARN",
        "reason": "Trust impartiality concern: portfolio yield < 2% and buying non-income security. Consider income beneficiary needs.",
        "rule": "account_type/trust.rego:check_trust_impartiality",
        "wsp_section": "WSP-9.3",
        "account_type": input.account_type,
        "portfolio_yield": input.portfolio_income_yield,
        "security_yield": input.security_yield,
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 2: Trust concentration limit (15%)
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Trust concentration check
# description: Warns when trust exceeds 15% single-position concentration
# custom:
#   wsp_section: "WSP-9.3"
#   gap: 5
#   severity: "WARN"
check_trust := result if {
    input.account_type in {"trust_revocable", "trust_irrevocable"}
    input.proposed_position_pct > 15
    result := {
        "decision": "WARN",
        "reason": sprintf(
            "Trust prudent investor: %.1f%% concentration exceeds 15%% guideline",
            [input.proposed_position_pct],
        ),
        "rule": "account_type/trust.rego:check_trust_concentration",
        "wsp_section": "WSP-9.3",
        "account_type": input.account_type,
        "proposed_pct": input.proposed_position_pct,
        "limit_pct": 15,
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 3: UGMA/UTMA — restricted investment types for minors
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: UGMA/UTMA restricted investment check
# description: Denies speculative investments in custodial minor accounts
# custom:
#   wsp_section: "WSP-9.3"
#   gap: 5
#   severity: "BLOCK"
check_trust := result if {
    input.account_type in {"ugma", "utma"}
    input.security_type in {"option", "future", "leveraged_etf", "cryptocurrency", "penny_stock"}
    result := {
        "decision": "DENY",
        "reason": sprintf(
            "UGMA/UTMA accounts prohibit speculative investments: %s",
            [input.security_type],
        ),
        "rule": "account_type/trust.rego:check_ugma_utma_restricted",
        "wsp_section": "WSP-9.3",
        "account_type": input.account_type,
        "security_type": input.security_type,
    }
}

# ═══════════════════════════════════════════════════════════════════
# RULE 4: Estate account — conservative mandate
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Estate account concentration check
# description: Warns on concentration in estate accounts (conservative mandate)
# custom:
#   wsp_section: "WSP-9.3"
#   gap: 5
#   severity: "WARN"
check_trust := result if {
    input.account_type == "estate"
    input.proposed_position_pct > 10
    result := {
        "decision": "WARN",
        "reason": sprintf(
            "Estate account conservative mandate: %.1f%% concentration exceeds 10%% guideline",
            [input.proposed_position_pct],
        ),
        "rule": "account_type/trust.rego:check_estate_concentration",
        "wsp_section": "WSP-9.3",
        "account_type": input.account_type,
        "proposed_pct": input.proposed_position_pct,
        "limit_pct": 10,
    }
}
