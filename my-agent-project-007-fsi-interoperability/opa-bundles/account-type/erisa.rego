# METADATA
# title: ERISA §406 prohibited-transaction checks (framework)
# description: |
#   ERISA §404 (prudent expert) + §406 (prohibited transactions)
#   framework rules. Full party-in-interest list is Phase 4
#   SME-gated data and is injected via data.party_in_interest_list.
# custom:
#   gap: 5
#   severity: "BLOCK"
#   wsp_section: "ERISA Policy §406"
package authority.account_type.erisa

import rego.v1

erisa_governed_set := {
    "401k",
    "403b",
    "457",
    "erisa_pension",
    "erisa_profit_sharing",
}

# METADATA
# title: prohibited_transaction_party_in_interest
# description: |
#   Fires when a proposed trade counterparty is on the firm's
#   party-in-interest list AND the account is ERISA-governed.
# custom:
#   wsp_section: "ERISA Policy §406"
#   rule_id: "authority.account_type.erisa.prohibited_transaction_party_in_interest"
prohibited_transaction_party_in_interest := result if {
    input.account_type in erisa_governed_set
    is_party_in_interest(input.counterparty_id)
    result := {
        "decision": "BLOCK",
        "reason": sprintf(
            "ERISA §406 prohibited transaction: %s is a party-in-interest",
            [input.counterparty_id],
        ),
        "rule_id": "authority.account_type.erisa.prohibited_transaction_party_in_interest",
        "wsp_section": "ERISA Policy §406",
    }
}

is_party_in_interest(entity_id) if {
    data.party_in_interest_list[entity_id]
}
