%dw 2.0
// Project 006 v2 - close-account response builder (mock backend).
// Generates a MS-REF-{12-hex} reference from a random UUID. No new account number minted.
// When real core-banking + custodian is wired, closed_at becomes the custodian's closure timestamp.
// Input: vars.normalized (produced by close-account-request.dwl).
// Output: application/json matching CloseAccountResponse from close-account.raml.
output application/json
var uuid = randomUUID() replace "-" with ""
---
{
  account_id: vars.normalized.account_id,
  status: "CLOSED",
  closed_at: (now() as Number {unit: "seconds"}) as Number {format: "#"},
  mulesoft_reference: "MS-REF-" ++ (uuid[0 to 11])
}
