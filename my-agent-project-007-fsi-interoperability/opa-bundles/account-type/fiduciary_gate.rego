# METADATA
# title: Fiduciary gate — block Reg BI doc path on retirement accounts
# description: |
#   When the firm's suitability_standard is "fiduciary" and the
#   account is in the RETIREMENT_SET, the Reg BI documentation code
#   path is blocked. Fiduciary best-interest documentation is
#   required instead.
# custom:
#   gap: 5
#   severity: "BLOCK"
#   wsp_section: "ERISA Policy §404(a)(1)(B)"
package authority.account_type.fiduciary_gate

import rego.v1

# 9-member retirement set. Must match
# src/compliance/gap5_erisa_account_type/taxonomy.py RETIREMENT_SET.
retirement_set := {
    "traditional_ira",
    "roth_ira",
    "sep_ira",
    "simple_ira",
    "401k",
    "403b",
    "457",
    "erisa_pension",
    "erisa_profit_sharing",
}

# METADATA
# title: reg_bi_blocked_on_retirement
# description: |
#   Fires when suitability_standard="fiduciary", the account is in
#   retirement_set, and the caller asks for the Reg BI doc path.
# custom:
#   wsp_section: "ERISA Policy §404(a)(1)(B)"
#   rule_id: "authority.account_type.fiduciary_gate.reg_bi_blocked_on_retirement"
reg_bi_blocked_on_retirement := result if {
    input.account_type in retirement_set
    input.suitability_standard == "fiduciary"
    input.proposed_doc_path == "reg_bi"
    result := {
        "decision": "BLOCK",
        "reason": sprintf(
            "fiduciary standard requires fiduciary doc for %s",
            [input.account_type],
        ),
        "rule_id": "authority.account_type.fiduciary_gate.reg_bi_blocked_on_retirement",
        "wsp_section": "ERISA Policy §404(a)(1)(B)",
    }
}
