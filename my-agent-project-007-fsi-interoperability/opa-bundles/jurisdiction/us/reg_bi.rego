# METADATA
# title: US Reg BI baseline overlay
# description: |
#   US jurisdiction baseline — SEC Regulation Best Interest §15l-1.
#   Same-jurisdiction egress within the US is ALLOW by default.
# custom:
#   gap: 7
#   jurisdiction: "us"
#   wsp_section: "Reg BI §15l-1"
package jurisdiction.us.reg_bi

import rego.v1

# METADATA
# title: us_same_jurisdiction_ok
# description: |
#   Fires when both primary and residency are US.
# custom:
#   wsp_section: "Reg BI §15l-1"
#   rule_id: "jurisdiction.us.reg_bi.us_same_jurisdiction_ok"
us_same_jurisdiction_ok := result if {
    input.primary_jurisdiction == "us"
    input.data_residency == "us"
    result := {
        "decision": "ALLOW",
        "rule_id": "jurisdiction.us.reg_bi.us_same_jurisdiction_ok",
        "wsp_section": "Reg BI §15l-1",
    }
}
