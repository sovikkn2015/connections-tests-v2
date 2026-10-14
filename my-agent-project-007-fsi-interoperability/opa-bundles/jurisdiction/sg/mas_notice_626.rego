# METADATA
# title: MAS Notice 626 marketing gate
# description: |
#   Singapore MAS Notice 626 §9 — retail marketing of restricted
#   product types (crypto, leveraged FX) is prohibited without
#   additional consents.
# custom:
#   gap: 7
#   jurisdiction: "sg"
#   wsp_section: "MAS Notice 626 §9"
package jurisdiction.sg.mas_notice_626

import rego.v1

mas_retail_restricted := {"crypto", "leveraged_fx"}

# METADATA
# title: mas_retail_restricted_product
# custom:
#   wsp_section: "MAS Notice 626 §9"
#   rule_id: "jurisdiction.sg.mas_notice_626.mas_retail_restricted_product"
mas_retail_restricted_product := result if {
    input.target_vendor_jurisdiction == "sg"
    input.client_classification == "retail"
    input.marketing_channel != "none"
    input.product_type in mas_retail_restricted
    result := {
        "decision": "DENY",
        "rule_id": "jurisdiction.sg.mas_notice_626.mas_retail_restricted_product",
        "wsp_section": "MAS Notice 626 §9",
    }
}
