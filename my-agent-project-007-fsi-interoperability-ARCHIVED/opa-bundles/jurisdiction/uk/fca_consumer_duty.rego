# METADATA
# title: FCA Consumer Duty (PS22/9)
# description: Deterministic OPA rules for FCA Consumer Duty — products and
#   services, price and value, consumer understanding, and consumer
#   support outcomes for UK-regulated firms.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   jurisdiction: "UK"
#   severity: "BLOCK"
package jurisdiction.uk.fca_consumer_duty

import rego.v1

# ── Products and services — target market alignment ──────────────

# METADATA
# title: FCA Consumer Duty — products and services outcome
# description: FCA Consumer Duty requires products to be designed to meet the
#   needs of the identified target market. WARN if product-target market
#   mismatch detected.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   severity: "WARN"
check_products_and_services := result if {
	input.jurisdiction == "UK"
	input.product_target_market_defined == true
	input.client_in_target_market == false
	result := {
		"decision": "WARN",
		"reason": "FCA Consumer Duty: product-target market mismatch — client outside identified target market.",
		"rule": "jurisdiction/uk/fca_consumer_duty.rego:check_products_and_services",
		"wsp_section": "10.4",
		"outcome": "products_and_services",
		"product_id": input.product_id,
		"target_market": input.target_market,
	}
}

# METADATA
# title: FCA Consumer Duty — target market not defined
# description: Products must have a defined target market before distribution.
#   BLOCK if target market is not defined.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   severity: "BLOCK"
check_products_target_market_missing := result if {
	input.jurisdiction == "UK"
	input.product_target_market_defined == false
	result := {
		"decision": "BLOCK",
		"reason": "FCA Consumer Duty: target market must be defined before product distribution.",
		"rule": "jurisdiction/uk/fca_consumer_duty.rego:check_products_target_market_missing",
		"wsp_section": "10.4",
		"outcome": "products_and_services",
		"product_id": input.product_id,
	}
}

# ── Price and value — fair value assessment required ─────────────

# METADATA
# title: FCA Consumer Duty — price and value outcome
# description: FCA Consumer Duty requires firms to assess whether products
#   provide fair value to consumers. WARN if fair value assessment has
#   not been completed.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   severity: "WARN"
check_price_and_value := result if {
	input.jurisdiction == "UK"
	input.fair_value_assessed == false
	result := {
		"decision": "WARN",
		"reason": "FCA Consumer Duty: fair value assessment required for product pricing.",
		"rule": "jurisdiction/uk/fca_consumer_duty.rego:check_price_and_value",
		"wsp_section": "10.4",
		"outcome": "price_and_value",
		"product_id": input.product_id,
	}
}

# ── Consumer understanding — communications must be clear ────────

# METADATA
# title: FCA Consumer Duty — consumer understanding outcome
# description: FCA Consumer Duty requires communications to be clear, fair,
#   and not misleading. Communications must be reviewed before distribution.
#   BLOCK if communication has not been reviewed.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   severity: "BLOCK"
check_consumer_understanding := result if {
	input.jurisdiction == "UK"
	input.communication_reviewed == false
	input.communication_type != ""
	result := {
		"decision": "BLOCK",
		"reason": "FCA Consumer Duty: communication must be reviewed for clarity before distribution.",
		"rule": "jurisdiction/uk/fca_consumer_duty.rego:check_consumer_understanding",
		"wsp_section": "10.4",
		"outcome": "consumer_understanding",
		"communication_type": input.communication_type,
	}
}

# METADATA
# title: FCA Consumer Duty — readability score below threshold
# description: FCA Consumer Duty requires communications to be understandable
#   by the target audience. Readability score (Flesch-Kincaid) must meet
#   minimum threshold of 60. BLOCK if score is below threshold.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   severity: "BLOCK"
check_consumer_understanding_readability := result if {
	input.jurisdiction == "UK"
	input.communication_reviewed == true
	input.readability_score < 60
	result := {
		"decision": "BLOCK",
		"reason": sprintf("FCA Consumer Duty: readability score %.1f below threshold 60. Communication not sufficiently clear.", [input.readability_score]),
		"rule": "jurisdiction/uk/fca_consumer_duty.rego:check_consumer_understanding_readability",
		"wsp_section": "10.4",
		"outcome": "consumer_understanding",
		"readability_score": input.readability_score,
		"threshold": 60,
	}
}

# ── Consumer support — adequate support channels required ────────

# METADATA
# title: FCA Consumer Duty — consumer support outcome
# description: FCA Consumer Duty requires firms to provide adequate support
#   channels. WARN if support channels are insufficient (fewer than 2
#   active channels).
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   severity: "WARN"
check_consumer_support := result if {
	input.jurisdiction == "UK"
	count(input.active_support_channels) < 2
	result := {
		"decision": "WARN",
		"reason": sprintf("FCA Consumer Duty: insufficient support channels (%d). Minimum 2 required.", [count(input.active_support_channels)]),
		"rule": "jurisdiction/uk/fca_consumer_duty.rego:check_consumer_support",
		"wsp_section": "10.4",
		"outcome": "consumer_support",
		"active_channels": count(input.active_support_channels),
		"minimum_required": 2,
	}
}
