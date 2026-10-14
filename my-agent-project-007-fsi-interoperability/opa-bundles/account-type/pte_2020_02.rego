# METADATA
# title: DOL PTE 2020-02 rollover enhanced-documentation rule
# description: |
#   Any rollover recommendation into a retirement account triggers
#   enhanced best-interest documentation per DOL PTE 2020-02.
# custom:
#   gap: 5
#   severity: "REQUIRE_ENHANCED_DOC"
#   wsp_section: "ERISA Policy §PTE 2020-02(b)"
package authority.account_type.pte_2020_02

import rego.v1

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
# title: rollover_requires_enhanced_doc
# description: |
#   Fires when is_rollover=true and account_type ∈ retirement_set.
# custom:
#   wsp_section: "ERISA Policy §PTE 2020-02(b)"
#   rule_id: "authority.account_type.pte_2020_02.rollover_requires_enhanced_doc"
rollover_requires_enhanced_doc := result if {
    input.is_rollover == true
    input.account_type in retirement_set
    result := {
        "decision": "REQUIRE_ENHANCED_DOC",
        "reason": sprintf(
            "PTE 2020-02 rollover into %s requires enhanced doc",
            [input.account_type],
        ),
        "rule_id": "authority.account_type.pte_2020_02.rollover_requires_enhanced_doc",
        "wsp_section": "ERISA Policy §PTE 2020-02(b)",
    }
}

# METADATA
# title: rollover_documentation_retention
# description: |
#   PTE 2020-02(e) — enhanced-documentation records must be retained
#   per §17a-4(e)(5) for minimum 6 years.
# custom:
#   wsp_section: "ERISA Policy §PTE 2020-02(e)"
#   rule_id: "authority.account_type.pte_2020_02.rollover_documentation_retention"
rollover_documentation_retention := result if {
    input.is_rollover == true
    input.account_type in retirement_set
    result := {
        "decision": "RETAIN_6Y",
        "wsp_section": "ERISA Policy §PTE 2020-02(e)",
        "rule_id": "authority.account_type.pte_2020_02.rollover_documentation_retention",
    }
}
