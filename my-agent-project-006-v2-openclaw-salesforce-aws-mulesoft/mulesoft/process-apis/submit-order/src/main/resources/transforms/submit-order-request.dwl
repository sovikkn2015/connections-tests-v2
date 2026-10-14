%dw 2.0
// Project 006 v2 - submit-order request normalizer.
// Passthrough-with-defaults for the mock backend.
// When a real OMS is wired, this is where broker-specific fields (TIF, route) get set.
// Input: application/json matching SubmitOrderRequest from submit-order.raml.
// Output: the internal normalized shape stored in vars.normalized.
output application/json
---
{
  ticker: payload.ticker,
  side: payload.side,
  quantity: payload.quantity,
  order_type: payload.order_type default "MARKET",
  limit_price: payload.limit_price default null,
  client_id: payload.client_id,
  account_id: payload.account_id,
  approval_token_hash: payload.approval_token_hash,
  // Internal provenance
  source: "mulesoft-actions-mcp",
  received_at: (now() as Number {unit: "seconds"}) as Number {format: "#"}
}
