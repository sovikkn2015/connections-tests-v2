%dw 2.0
// Project 006 v3 - initiate-wire canonical -> Dwolla POST /transfers body.
//
// Dwolla sandbox transfers expect:
//   {
//     _links: { source: { href }, destination: { href } },
//     amount: { currency, value }
//   }
//
// For demo purposes we synthesize href values from source_account_id and
// beneficiary_account. In a real integration the Dwolla funding-source
// resource URIs would be looked up from a mapping table.
output application/json
var base = "https://api-sandbox.dwolla.com/funding-sources/"
---
{
  "_links": {
    "source": {
      "href": base ++ vars.normalized.source_account_id
    },
    "destination": {
      "href": base ++ vars.normalized.beneficiary_account
    }
  },
  "amount": {
    "currency": vars.normalized.currency default "USD",
    "value": vars.normalized.amount_usd as String
  }
}
++ (
  if (vars.normalized.reference_memo != null and vars.normalized.reference_memo != "")
    { metadata: { memo: vars.normalized.reference_memo } }
  else
    {}
)
