%dw 2.0
// Project 006 v3 - submit-order Alpaca response -> canonical SubmitOrderResponse.
//
// Input:  payload = Alpaca response body
//         vars.normalized = the canonical request (authoritative for ticker/side/qty)
//
// Output: canonical SubmitOrderResponse per submit-order.raml:
//           { order_id, status, ticker, side, quantity, submitted_at, mulesoft_reference }
//
// Mapping:
//   Alpaca id         -> "ALPACA-{id}" (prefix distinguishes live from mock)
//   Alpaca status     -> pass-through (accepted/new/filled/... all valid)
//   ticker/side/qty   -> from vars.normalized (trust our input)
//   Alpaca created_at -> parsed ISO 8601 -> unix seconds
//   mulesoft_reference -> fresh MS-REF-{12hex}; owned by this flow, not Alpaca
import * from dw::Runtime
import * from dw::Crypto
output application/json
var uuid = dw::Crypto::SHA1((now() as String) as Binary) replace "-" with ""
---
{
  order_id: "ALPACA-" ++ (payload.id default ("UNKNOWN-" ++ uuid[0 to 7])),
  status: payload."status" default "accepted",
  ticker: vars.normalized.ticker,
  side: vars.normalized.side,
  quantity: vars.normalized.quantity,
  submitted_at: (
    if (payload.created_at != null)
      ((((payload.created_at[0 to 18]) as LocalDateTime {format: "yyyy-MM-dd'T'HH:mm:ss"}) >> "UTC") as Number {unit: "seconds"}) as Number {format: "#"}
    else
      (now() as Number {unit: "seconds"}) as Number {format: "#"}
  ),
  mulesoft_reference: "MS-REF-" ++ (uuid[0 to 11])
}
