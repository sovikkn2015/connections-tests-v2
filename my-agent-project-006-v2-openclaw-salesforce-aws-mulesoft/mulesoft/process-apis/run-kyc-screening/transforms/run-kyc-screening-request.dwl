%dw 2.0
// Project 006 v2 - run-kyc-screening request normalizer.
// Passthrough-with-defaults for the mock backend.
// When real vendor (LexisNexis Bridger, Refinitiv World-Check) is wired, this is where
// PII hashing, jurisdiction selection, and vendor-specific search parameters get set.
// Input: application/json matching KycRequest from run-kyc-screening.raml.
// Output: the internal normalized shape stored in vars.normalized.
output application/json
---
{
  client_name: payload.client_name,
  level: payload.level,
  checks: payload.checks default ["sanctions", "pep"],
  approval_token_hash: payload.approval_token_hash,
  // Internal provenance
  source: "mulesoft-actions-mcp",
  received_at: (now() as Number {unit: "seconds"}) as Number {format: "#"}
}
