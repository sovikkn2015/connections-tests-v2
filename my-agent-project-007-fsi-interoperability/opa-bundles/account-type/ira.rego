# METADATA
# title: IRA-specific gating rules (IRC 4975 overlay)
# description: |
#   IRA prohibited-transaction overlay under IRC §4975. Mirrors the
#   ERISA §406 framework but with IRC authority.
# custom:
#   gap: 5
#   severity: "BLOCK"
#   wsp_section: "ERISA Policy §IRC 4975"
package authority.account_type.ira

import rego.v1

ira_set := {
    "traditional_ira",
    "roth_ira",
    "sep_ira",
    "simple_ira",
}

# METADATA
# title: irc_4975_prohibited_transaction
# description: |
#   Fires when a proposed trade is self-dealing under IRC §4975.
# custom:
#   wsp_section: "ERISA Policy §IRC 4975"
#   rule_id: "authority.account_type.ira.irc_4975_prohibited_transaction"
irc_4975_prohibited_transaction := result if {
    input.account_type in ira_set
    input.self_dealing == true
    result := {
        "decision": "BLOCK",
        "reason": "IRC §4975 prohibited transaction: self-dealing",
        "rule_id": "authority.account_type.ira.irc_4975_prohibited_transaction",
        "wsp_section": "ERISA Policy §IRC 4975",
    }
}
