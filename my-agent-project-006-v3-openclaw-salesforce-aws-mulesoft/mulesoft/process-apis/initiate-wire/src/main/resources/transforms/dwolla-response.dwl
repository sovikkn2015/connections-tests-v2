%dw 2.0
// Project 006 v3 - initiate-wire Dwolla response -> canonical InitiateWireResponse.
//
// Dwolla returns 201 Created with a Location header: /transfers/{id}.
// attributes.headers."location" captures that. The response body is typically
// empty on 201; id is parsed from the Location header.
import * from dw::Runtime
import * from dw::Crypto
output application/json
var uuid = dw::Crypto::SHA1((now() as String) as Binary) replace "-" with ""
var loc = attributes.headers."location" default ""
var transferId = if (loc contains "/transfers/") (loc splitBy "/transfers/")[1] else ("UNKNOWN-" ++ uuid[0 to 7])
---
{
  wire_id: "DWOLLA-" ++ transferId,
  status: "initiated",
  amount_usd: vars.normalized.amount_usd,
  currency: vars.normalized.currency default "USD",
  beneficiary_bank: vars.normalized.beneficiary_bank,
  beneficiary_account: vars.normalized.beneficiary_account,
  source_account_id: vars.normalized.source_account_id,
  submitted_at: (now() as Number {unit: "seconds"}) as Number {format: "#"},
  mulesoft_reference: "MS-REF-" ++ (uuid[0 to 11])
}
