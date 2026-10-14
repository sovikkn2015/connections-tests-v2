%dw 2.0
// Project 006 v2 - initiate-wire response builder (mock backend).
// Generates a MULE-WIRE-{8-hex} id and a MS-REF-{12-hex} reference from a single UUID.
// When real SWIFT/Fedwire comes online, wire_id becomes the network's transaction reference
// (e.g., IMAD/OMAD for Fedwire, MUR for SWIFT) and the mock branch is removed.
// Input: vars.normalized (produced by initiate-wire-request.dwl).
// Output: application/json matching InitiateWireResponse from initiate-wire.raml.
output application/json
var uuid = randomUUID() replace "-" with ""
---
{
  wire_id: "MULE-WIRE-" ++ (uuid[0 to 7]),
  status: "INITIATED",
  amount: vars.normalized.amount,
  currency: vars.normalized.currency,
  from_account: vars.normalized.from_account,
  to_account: vars.normalized.to_account,
  submitted_at: (now() as Number {unit: "seconds"}) as Number {format: "#"},
  mulesoft_reference: "MS-REF-" ++ (uuid[0 to 11])
}
