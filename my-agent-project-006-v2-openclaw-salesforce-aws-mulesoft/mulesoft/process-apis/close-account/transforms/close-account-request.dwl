%dw 2.0
// Project 006 v2 - close-account request normalizer.
// Passthrough-with-defaults for the mock backend.
// When real core-banking + custodian is wired, this is where residual-balance sweep rules,
// tax-lot closure, and proceeds-destination routing would be resolved.
// Input: application/json matching CloseAccountRequest from close-account.raml.
// Output: the internal normalized shape stored in vars.normalized.
output application/json
---
{
  client_id: payload.client_id,
  account_id: payload.account_id,
  reason: payload.reason,
  approval_token_hash: payload.approval_token_hash,
  dual_approval_token_hash: payload.dual_approval_token_hash,
  // Internal provenance
  source: "mulesoft-actions-mcp",
  received_at: (now() as Number {unit: "seconds"}) as Number {format: "#"}
}
