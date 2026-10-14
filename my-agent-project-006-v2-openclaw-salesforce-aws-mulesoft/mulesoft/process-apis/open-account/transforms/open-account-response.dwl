%dw 2.0
// Project 006 v2 - open-account response builder (mock backend).
// Generates a MULE-ACCT-{10-hex, uppercased} account number and a MS-REF-{12-hex} reference.
// When real core-banking + custodian is wired, account_number becomes the custodian's primary key.
// Input: vars.normalized (produced by open-account-request.dwl).
// Output: application/json matching OpenAccountResponse from open-account.raml.
output application/json
var uuid = randomUUID() replace "-" with ""
---
{
  account_number: "MULE-ACCT-" ++ upper(uuid[0 to 9]),
  status: "OPEN",
  account_type: vars.normalized.account_type,
  jurisdiction: vars.normalized.jurisdiction,
  opened_at: (now() as Number {unit: "seconds"}) as Number {format: "#"},
  mulesoft_reference: "MS-REF-" ++ (uuid[0 to 11])
}
