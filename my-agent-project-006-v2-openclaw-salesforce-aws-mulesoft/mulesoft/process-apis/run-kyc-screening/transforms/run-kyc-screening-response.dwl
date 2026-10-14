%dw 2.0
// Project 006 v2 - run-kyc-screening response builder (mock backend).
// Generates a MULE-KYC-{8-hex} id and a MS-REF-{12-hex} reference from a single UUID.
// Mock rule: sanctions=CLEAR, pep=CLEAR always. adverse_media=REVIEW only at ENHANCED level.
// When real vendor comes online, the results map is populated from the vendor's match rows.
// Input: vars.normalized (produced by run-kyc-screening-request.dwl).
// Output: application/json matching KycResponse from run-kyc-screening.raml.
output application/json
var uuid = randomUUID() replace "-" with ""
var lvl = vars.normalized.level
var results = (vars.normalized.checks default []) reduce ((chk, acc={}) ->
  acc ++ {
    (chk): if (chk == "adverse_media" and lvl == "ENHANCED") "REVIEW" else "CLEAR"
  }
)
---
{
  screening_id: "MULE-KYC-" ++ (uuid[0 to 7]),
  status: "COMPLETED",
  client_name: vars.normalized.client_name,
  level: vars.normalized.level,
  results: results,
  screened_at: (now() as Number {unit: "seconds"}) as Number {format: "#"},
  mulesoft_reference: "MS-REF-" ++ (uuid[0 to 11])
}
