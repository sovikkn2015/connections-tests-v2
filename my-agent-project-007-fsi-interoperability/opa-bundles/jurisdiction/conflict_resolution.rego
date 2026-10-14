# METADATA
# title: Cross-jurisdiction conflict resolution
# description: |
#   Resolves GDPR Art. 17 erasure vs 17 CFR §240.17a-4(e)(5)
#   retention. Regulated records retained over erasure.
# custom:
#   gap: 7
#   wsp_section: "GDPR Art. 17(3)(b)"
package jurisdiction.conflict_resolution

import rego.v1

# METADATA
# title: erasure_vs_retention
# custom:
#   wsp_section: "GDPR Art. 17(3)(b)"
#   rule_id: "jurisdiction.conflict_resolution.erasure_vs_retention"
erasure_vs_retention := result if {
    input.request_type == "gdpr_erasure"
    input.data_category == "regulated_record"
    result := {
        "decision": "DENY_ERASURE",
        "reason": "regulated record subject to retention (17a-4 / MiFID II)",
        "rule_id": "jurisdiction.conflict_resolution.erasure_vs_retention",
        "wsp_section": "GDPR Art. 17(3)(b)",
    }
}

# METADATA
# title: retention_clock
# description: |
#   Minimum 6-year retention for regulated records per 17 CFR
#   §240.17a-4(e)(5).
# custom:
#   wsp_section: "17 CFR §240.17a-4(e)(5)"
#   rule_id: "jurisdiction.conflict_resolution.retention_clock"
retention_clock := result if {
    input.data_category == "regulated_record"
    result := {
        "decision": "RETAIN_6Y",
        "rule_id": "jurisdiction.conflict_resolution.retention_clock",
        "wsp_section": "17 CFR §240.17a-4(e)(5)",
    }
}
