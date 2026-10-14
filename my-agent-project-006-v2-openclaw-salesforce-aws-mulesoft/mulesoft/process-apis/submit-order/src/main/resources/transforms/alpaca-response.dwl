%dw 2.0
// Project 006 v2 - submit-order Alpaca response -> canonical SubmitOrderResponse.
//
// Input:  payload = JSON body returned by Alpaca POST /v2/orders:
//           {
//             id, client_order_id, created_at, updated_at,
//             symbol, qty, side, type, time_in_force, status, ...
//           }
//         vars.normalized (the canonical request we built earlier, used as
//           a safety net for ticker/side/quantity if Alpaca omits any).
//
// Output: canonical SubmitOrderResponse per submit-order.raml:
//           { order_id, status, ticker, side, quantity, submitted_at,
//             mulesoft_reference }
//
// Mapping:
//   Alpaca id          -> canonical order_id (we prefix with "ALPACA-" so the
//                          Lambda / audit log can tell live ids from mock
//                          "MULE-ORDER-..." ids at a glance)
//   Alpaca status      -> canonical status   (pass-through; "accepted", "new",
//                          "filled", etc. are all valid per Alpaca state machine)
//   canonical ticker   -> copied from vars.normalized.ticker (authoritative;
//                          Alpaca's "symbol" should match but we trust our input)
//   canonical side     -> vars.normalized.side (uppercase BUY/SELL)
//   canonical quantity -> vars.normalized.quantity (integer)
//   Alpaca created_at  -> canonical submitted_at (ISO 8601 -> unix seconds)
//   mulesoft_reference -> freshly minted "MS-REF-{12hex}" from this flow, not
//                          Alpaca's id. This is OUR reference for the audit log.
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
  // Alpaca returns created_at as ISO 8601 (fractional seconds variable length).
  // Parse as LocalDateTime then attach UTC zone, then coerce to epoch seconds.
  submitted_at: (
    if (payload.created_at != null)
      ((((payload.created_at[0 to 18]) as LocalDateTime {format: "yyyy-MM-dd'T'HH:mm:ss"}) >> "UTC") as Number {unit: "seconds"}) as Number {format: "#"}
    else
      (now() as Number {unit: "seconds"}) as Number {format: "#"}
  ),
  mulesoft_reference: "MS-REF-" ++ (uuid[0 to 11])
}
