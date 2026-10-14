# METADATA
# title: GDPR Art. 6(1) lawful-basis evaluator
# description: |
#   Six lawful bases under GDPR Art. 6(1)(a)..(f). Gap 7 Python
#   executes this truth table; the Rego rules are the policy
#   source-of-record for a future OPA cutover.
# custom:
#   gap: 7
#   jurisdiction: "eu"
#   wsp_section: "GDPR Art. 6(1)(a)"
package jurisdiction.eu.gdpr_lawful_basis

import rego.v1

# METADATA
# title: consent_basis_missing_consent
# description: |
#   Fires when basis=consent and consent_on_file=false.
# custom:
#   wsp_section: "GDPR Art. 6(1)(a)"
#   rule_id: "jurisdiction.eu.gdpr_lawful_basis.consent_basis_missing_consent"
consent_basis_missing_consent := result if {
    input.lawful_basis == "consent"
    input.consent_on_file == false
    result := {
        "decision": "REQUIRE_CONSENT",
        "rule_id": "jurisdiction.eu.gdpr_lawful_basis.consent_basis_missing_consent",
        "wsp_section": "GDPR Art. 6(1)(a)",
    }
}

# METADATA
# title: contract_basis_requires_scc
# description: |
#   Fires when basis=contract, EU subject present, no SCC on file.
# custom:
#   wsp_section: "GDPR Art. 6(1)(b)"
#   rule_id: "jurisdiction.eu.gdpr_lawful_basis.contract_basis_requires_scc"
contract_basis_requires_scc := result if {
    input.lawful_basis == "contract"
    input.involves_eu_data_subject == true
    input.scc_on_file == false
    result := {
        "decision": "REQUIRE_SCC",
        "rule_id": "jurisdiction.eu.gdpr_lawful_basis.contract_basis_requires_scc",
        "wsp_section": "GDPR Art. 6(1)(b)",
    }
}

# METADATA
# title: legitimate_interests_requires_scc
# description: |
#   Fires when basis=legitimate_interests, EU subject present, no SCC.
# custom:
#   wsp_section: "GDPR Art. 6(1)(f)"
#   rule_id: "jurisdiction.eu.gdpr_lawful_basis.legitimate_interests_requires_scc"
legitimate_interests_requires_scc := result if {
    input.lawful_basis == "legitimate_interests"
    input.involves_eu_data_subject == true
    input.scc_on_file == false
    result := {
        "decision": "REQUIRE_SCC",
        "rule_id": "jurisdiction.eu.gdpr_lawful_basis.legitimate_interests_requires_scc",
        "wsp_section": "GDPR Art. 6(1)(f)",
    }
}

# METADATA
# title: cross_border_eu_transfer_requires_basis
# description: |
#   Any EU->non-EU transfer requires Art. 46 mechanism (SCC, adequacy,
#   BCR). Surfaced as REQUIRE_SCC when SCC is absent.
# custom:
#   wsp_section: "GDPR Art. 46"
#   rule_id: "jurisdiction.eu.gdpr_lawful_basis.cross_border_eu_transfer_requires_basis"
cross_border_eu_transfer_requires_basis := result if {
    input.primary_jurisdiction == "eu"
    input.target_vendor_jurisdiction != "eu"
    input.scc_on_file == false
    result := {
        "decision": "REQUIRE_SCC",
        "rule_id": "jurisdiction.eu.gdpr_lawful_basis.cross_border_eu_transfer_requires_basis",
        "wsp_section": "GDPR Art. 46",
    }
}
