# METADATA
# title: FINRA Suitability / Reg BI Rules
# description: Deterministic OPA rules for FINRA suitability obligations and
#   Reg BI applicability — registration type checks, concentration limits,
#   and restricted list enforcement.
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   jurisdiction: "US"
#   severity: "BLOCK"
package jurisdiction.us.finra_suitability

import rego.v1

# ── Reg BI applicability — BD/dual retail only ───────────────────

# METADATA
# title: Reg BI applicability check
# description: Reg BI applies to broker-dealers and dual-registered firms
#   serving retail customers only. Pure RIAs have fiduciary duty.
#   Institutional clients are excluded from Reg BI.
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   severity: "BLOCK"
check_reg_bi_applicability := result if {
	input.jurisdiction == "US"
	input.registration_type in {"bd_only", "dual_registered"}
	input.client_archetype == "retail"
	input.reg_bi_documentation_complete == false
	result := {
		"decision": "BLOCK",
		"reason": "Reg BI: documentation required for BD/dual-registered retail recommendations.",
		"rule": "jurisdiction/us/finra_suitability.rego:check_reg_bi_applicability",
		"wsp_section": "10.1",
		"registration_type": input.registration_type,
		"client_archetype": input.client_archetype,
	}
}

# ── Concentration limit — default 15%, ERISA 10% ────────────────

# METADATA
# title: Position concentration limit — default 15%
# description: Single-security position must not exceed 15% of account value
#   for standard accounts. ERISA accounts have a stricter 10% limit
#   per DOL guidelines.
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   severity: "BLOCK"
check_concentration := result if {
	input.jurisdiction == "US"
	not _is_erisa(input.account_type)
	input.position_pct > 15
	result := {
		"decision": "BLOCK",
		"reason": sprintf("Concentration limit exceeded: %.1f%% > 15%% for %s account.", [input.position_pct, input.account_type]),
		"rule": "jurisdiction/us/finra_suitability.rego:check_concentration",
		"wsp_section": "10.1",
		"position_pct": input.position_pct,
		"limit_pct": 15,
		"account_type": input.account_type,
	}
}

# METADATA
# title: ERISA concentration limit — 10%
# description: ERISA account positions must not exceed 10% concentration
#   per DOL fiduciary guidelines. Stricter than standard 15% limit.
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   severity: "BLOCK"
check_concentration_erisa := result if {
	input.jurisdiction == "US"
	_is_erisa(input.account_type)
	input.position_pct > 10
	result := {
		"decision": "BLOCK",
		"reason": sprintf("ERISA concentration limit exceeded: %.1f%% > 10%% for %s account.", [input.position_pct, input.account_type]),
		"rule": "jurisdiction/us/finra_suitability.rego:check_concentration_erisa",
		"wsp_section": "10.1",
		"position_pct": input.position_pct,
		"limit_pct": 10,
		"account_type": input.account_type,
	}
}

# ── Restricted list — blocked if on list ─────────────────────────

# METADATA
# title: Restricted securities list check
# description: Denies trades in securities on the firm restricted list.
#   Fail-closed design — if security appears on restricted list, trade is blocked.
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   severity: "BLOCK"
check_restricted_list := result if {
	input.jurisdiction == "US"
	input.security_id in input.restricted_list
	result := {
		"decision": "BLOCK",
		"reason": sprintf("Security %s is on the firm restricted list. Trading blocked.", [input.security_id]),
		"rule": "jurisdiction/us/finra_suitability.rego:check_restricted_list",
		"wsp_section": "10.1",
		"security_id": input.security_id,
	}
}

# ── Helper: ERISA account type detection ─────────────────────────

_is_erisa(account_type) if account_type in {"401k", "403b", "457b", "erisa_pension"}
