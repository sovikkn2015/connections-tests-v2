%dw 2.0
// Project 006 v2 - submit-order response builder (mock backend).
// Generates a MULE-ORDER-{8-hex} id and a MS-REF-{12-hex} reference from a single UUID.
// When real OMS comes online, order_id will be the broker's ack id and the mock branch removed.
// Input: vars.normalized (produced by submit-order-request.dwl).
// Output: application/json matching SubmitOrderResponse from submit-order.raml.
output application/json
var uuid = randomUUID() replace "-" with ""
---
{
  order_id: "MULE-ORDER-" ++ (uuid[0 to 7]),
  status: "SUBMITTED",
  ticker: vars.normalized.ticker,
  side: vars.normalized.side,
  quantity: vars.normalized.quantity,
  submitted_at: (now() as Number {unit: "seconds"}) as Number {format: "#"},
  mulesoft_reference: "MS-REF-" ++ (uuid[0 to 11])
}
