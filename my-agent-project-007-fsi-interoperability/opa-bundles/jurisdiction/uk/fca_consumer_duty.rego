# METADATA
# title: UK FCA Consumer Duty overlay (thin)
# description: |
#   FCA PRIN 2A — Consumer Duty: firms must act to deliver good
#   outcomes for retail customers. Phase-3 shell; full outcomes
#   tracker is Phase 5.
# custom:
#   gap: 7
#   jurisdiction: "uk"
#   wsp_section: "FCA Consumer Duty PRIN 2A"
package jurisdiction.uk.fca_consumer_duty

import rego.v1

# METADATA
# title: uk_same_jurisdiction_ok
# custom:
#   wsp_section: "FCA Consumer Duty PRIN 2A"
#   rule_id: "jurisdiction.uk.fca_consumer_duty.uk_same_jurisdiction_ok"
uk_same_jurisdiction_ok := result if {
    input.primary_jurisdiction == "uk"
    input.data_residency == "uk"
    result := {
        "decision": "ALLOW",
        "rule_id": "jurisdiction.uk.fca_consumer_duty.uk_same_jurisdiction_ok",
        "wsp_section": "FCA Consumer Duty PRIN 2A",
    }
}
