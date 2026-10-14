# account-type/trust_test.rego — OPA native tests for Trust & Custodial rules (Gap 5)
#
# Tests:
#   1. Trust impartiality — low yield + non-income security → WARN
#   2. Trust impartiality — adequate yield → PASS
#   3. UGMA/UTMA restricted — speculative investment → DENY
#   4. UGMA/UTMA restricted — standard investment → PASS
#   5. Estate concentration — >10% → WARN
#   6. Default pass — non-trust account
#
# Every rule includes wsp_section annotation (steering rule 19).

package account_type.trust_test

import rego.v1

import data.account_type.trust

# ═══════════════════════════════════════════════════════════════════
# TEST: Trust impartiality — low yield + non-income security → WARN
# ═══════════════════════════════════════════════════════════════════

test_impartiality_warns_low_yield_non_income if {
    result := trust.check_trust with input as {
        "account_type": "trust_irrevocable",
        "trust_has_income_beneficiary": true,
        "trust_has_remainder_beneficiary": true,
        "portfolio_income_yield": 0.015,
        "security_yield": 0,
        "proposed_position_pct": 5,
        "security_type": "equity",
    }
    result.decision == "WARN"
    contains(result.reason, "impartiality")
    result.wsp_section == "WSP-9.3"
}

test_impartiality_passes_adequate_yield if {
    result := trust.check_trust with input as {
        "account_type": "trust_revocable",
        "trust_has_income_beneficiary": true,
        "trust_has_remainder_beneficiary": true,
        "portfolio_income_yield": 0.035,
        "security_yield": 0,
        "proposed_position_pct": 5,
        "security_type": "equity",
    }
    result.decision == "PASS"
}

test_impartiality_passes_income_security if {
    result := trust.check_trust with input as {
        "account_type": "trust_irrevocable",
        "trust_has_income_beneficiary": true,
        "trust_has_remainder_beneficiary": true,
        "portfolio_income_yield": 0.01,
        "security_yield": 0.04,
        "proposed_position_pct": 5,
        "security_type": "bond",
    }
    result.decision == "PASS"
}

# ═══════════════════════════════════════════════════════════════════
# TEST: UGMA/UTMA restricted — speculative investments DENY
# ═══════════════════════════════════════════════════════════════════

test_ugma_denies_options if {
    result := trust.check_trust with input as {
        "account_type": "ugma",
        "security_type": "option",
        "proposed_position_pct": 5,
    }
    result.decision == "DENY"
    contains(result.reason, "speculative")
    result.wsp_section == "WSP-9.3"
}

test_ugma_denies_cryptocurrency if {
    result := trust.check_trust with input as {
        "account_type": "utma",
        "security_type": "cryptocurrency",
        "proposed_position_pct": 5,
    }
    result.decision == "DENY"
    contains(result.reason, "speculative")
}

test_ugma_denies_leveraged_etf if {
    result := trust.check_trust with input as {
        "account_type": "ugma",
        "security_type": "leveraged_etf",
        "proposed_position_pct": 5,
    }
    result.decision == "DENY"
}

test_ugma_allows_standard_equity if {
    result := trust.check_trust with input as {
        "account_type": "ugma",
        "security_type": "equity",
        "proposed_position_pct": 5,
    }
    result.decision == "PASS"
}

test_utma_allows_bond if {
    result := trust.check_trust with input as {
        "account_type": "utma",
        "security_type": "bond",
        "proposed_position_pct": 5,
    }
    result.decision == "PASS"
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Estate concentration — conservative mandate
# ═══════════════════════════════════════════════════════════════════

test_estate_concentration_above_10_warns if {
    result := trust.check_trust with input as {
        "account_type": "estate",
        "proposed_position_pct": 15,
        "security_type": "equity",
    }
    result.decision == "WARN"
    contains(result.reason, "Estate")
    contains(result.reason, "concentration")
    result.wsp_section == "WSP-9.3"
}

test_estate_concentration_at_10_passes if {
    result := trust.check_trust with input as {
        "account_type": "estate",
        "proposed_position_pct": 10,
        "security_type": "equity",
    }
    result.decision == "PASS"
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Default pass — non-trust account type
# ═══════════════════════════════════════════════════════════════════

test_non_trust_account_passes if {
    result := trust.check_trust with input as {
        "account_type": "individual_brokerage",
        "proposed_position_pct": 50,
        "security_type": "option",
    }
    result.decision == "PASS"
}
