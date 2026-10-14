# METADATA
# title: HKMA / SFC marketing gate
# description: |
#   Hong Kong SFC Code of Conduct §5.1A — marketing of complex
#   products to non-professionals requires KYC on file. Additionally,
#   SFC Part XIVA covers cross-border MNPI on SFC order IDs.
# custom:
#   gap: 7
#   jurisdiction: "hk"
#   wsp_section: "SFC Code of Conduct §5.1A"
package jurisdiction.hk.hkma_sfc_marketing

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
# title: sfc_complex_no_kyc
# custom:
#   wsp_section: "SFC Code of Conduct §5.1A"
#   rule_id: "jurisdiction.hk.hkma_sfc_marketing.sfc_complex_no_kyc"
sfc_complex_no_kyc := result if {
    input.target_vendor_jurisdiction == "hk"
    input.client_classification != "professional"
    input.product_type in complex_products
    input.kyc_on_file == false
    result := {
        "decision": "DENY",
        "rule_id": "jurisdiction.hk.hkma_sfc_marketing.sfc_complex_no_kyc",
        "wsp_section": "SFC Code of Conduct §5.1A",
    }
}

# METADATA
# title: sfc_mnpi_cross_border
# description: |
#   SFC Part XIVA — MNPI (sfc_order_id, hk_block_trade_size) must
#   not leave HK.
# custom:
#   wsp_section: "SFC Part XIVA"
#   rule_id: "jurisdiction.hk.hkma_sfc_marketing.sfc_mnpi_cross_border"
sfc_mnpi_cross_border := result if {
    input.primary_jurisdiction == "hk"
    input.target_vendor_jurisdiction != "hk"
    some f in input.payload_fields
    f in {"sfc_order_id", "hk_block_trade_size"}
    result := {
        "decision": "DENY",
        "rule_id": "jurisdiction.hk.hkma_sfc_marketing.sfc_mnpi_cross_border",
        "wsp_section": "SFC Part XIVA",
    }
}
