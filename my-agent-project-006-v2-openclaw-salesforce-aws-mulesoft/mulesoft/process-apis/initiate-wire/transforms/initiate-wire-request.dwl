%dw 2.0
// Project 006 v2 - initiate-wire request normalizer.
// Passthrough-with-defaults for the mock backend.
// When real SWIFT/Fedwire is wired, this is where BIC codes, correspondent banks, and
// settlement rails get resolved. Today it just carries the fields through unchanged.
// Input: application/json matching InitiateWireRequest from initiate-wire.raml.
// Output: the internal normalized shape stored in vars.normalized.
output application/json
---
{
  client_id: payload.client_id,
  from_account: payload.from_account,
  to_account: payload.to_account,
  amount: payload.amount,
  currency: payload.currency,
  priority: payload.priority default "STANDARD",
  approval_token_hash: payload.approval_token_hash,
  dual_approval_token_hash: payload.dual_approval_token_hash default null,
  // Internal provenance
  source: "mulesoft-actions-mcp",
  received_at: (now() as Number {unit: "seconds"}) as Number {format: "#"}
}
