%dw 2.0
// Project 006 v2 - rebalance-portfolio request normalizer.
// Passthrough-with-defaults for the mock backend.
// When real OMS batch integration is wired, this is where child-order generation, allocation
// strategy (proportional vs waterfall), and IOI matching would happen.
// Input: application/json matching RebalanceRequest from rebalance-portfolio.raml.
// Output: the internal normalized shape stored in vars.normalized.
output application/json
---
{
  client_id: payload.client_id,
  trades: payload.trades,
  trade_count: sizeOf(payload.trades default []),
  total_quantity: sum((payload.trades default []) map ($.quantity default 0)),
  approval_token_hash: payload.approval_token_hash,
  dual_approval_token_hash: payload.dual_approval_token_hash default null,
  // Internal provenance
  source: "mulesoft-actions-mcp",
  received_at: (now() as Number {unit: "seconds"}) as Number {format: "#"}
}
