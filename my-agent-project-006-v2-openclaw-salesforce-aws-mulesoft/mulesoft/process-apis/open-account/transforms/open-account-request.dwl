%dw 2.0
// Project 006 v2 - open-account request normalizer.
// Passthrough-with-defaults for the mock backend.
// When real core-banking + custodian is wired, this is where the CIP flag, FATCA/CRS status,
// and custodian-specific account-template selection would land.
// Input: application/json matching OpenAccountRequest from open-account.raml.
// Output: the internal normalized shape stored in vars.normalized.
output application/json
---
{
  client_id: payload.client_id,
  account_type: payload.account_type,
  jurisdiction: payload.jurisdiction,
  risk_profile: payload.risk_profile default null,
  approval_token_hash: payload.approval_token_hash,
  // Internal provenance
  source: "mulesoft-actions-mcp",
  received_at: (now() as Number {unit: "seconds"}) as Number {format: "#"}
}
