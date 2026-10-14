# METADATA
# title: MiFID II product-governance gate
# description: |
#   MiFID II Art. 25(2)/(3) — retail investors require a suitability
#   / knowledge-and-experience assessment before recommendations on
#   complex products.
# custom:
#   gap: 7
#   jurisdiction: "eu"
#   wsp_section: "MiFID II Art. 25(2)"
package jurisdiction.eu.mifid2_suitability

import rego.v1

complex_products := {
    "derivatives",
    "structured_notes",
    "leveraged_etf",
    "crypto",
    "leveraged_fx",
    "contingent_convertibles",
}

# METADATA
# title: retail_complex_no_suitability
# custom:
#   wsp_section: "MiFID II Art. 25(2)"
#   rule_id: "jurisdiction.eu.mifid2_suitability.retail_complex_no_suitability"
retail_complex_no_suitability := result if {
    input.client_classification == "retail"
    input.product_type in complex_products
    input.knowledge_experience_assessed == false
    result := {
        "decision": "DENY",
        "rule_id": "jurisdiction.eu.mifid2_suitability.retail_complex_no_suitability",
        "wsp_section": "MiFID II Art. 25(2)",
    }
}

# METADATA
# title: retail_no_knowledge_assessment
# custom:
#   wsp_section: "MiFID II Art. 25(3)"
#   rule_id: "jurisdiction.eu.mifid2_suitability.retail_no_knowledge_assessment"
retail_no_knowledge_assessment := result if {
    input.client_classification == "retail"
    input.knowledge_experience_assessed == false
    result := {
        "decision": "DENY",
        "rule_id": "jurisdiction.eu.mifid2_suitability.retail_no_knowledge_assessment",
        "wsp_section": "MiFID II Art. 25(3)",
    }
}
