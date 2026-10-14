%dw 2.0
// Project 006 v2 - rebalance-portfolio response builder (mock backend).
// Generates a MULE-BASKET-{8-hex} id and a MS-REF-{12-hex} reference from a single UUID.
// When real OMS is wired, basket_id becomes the parent-order id in the broker's system.
// Input: vars.normalized (produced by rebalance-portfolio-request.dwl).
// Output: application/json matching RebalanceResponse from rebalance-portfolio.raml.
output application/json
var uuid = randomUUID() replace "-" with ""
---
{
  basket_id: "MULE-BASKET-" ++ (uuid[0 to 7]),
  status: "SUBMITTED",
  client_id: vars.normalized.client_id,
  trade_count: vars.normalized.trade_count,
  submitted_at: (now() as Number {unit: "seconds"}) as Number {format: "#"},
  mulesoft_reference: "MS-REF-" ++ (uuid[0 to 11])
}
