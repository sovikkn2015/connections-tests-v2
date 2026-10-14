%dw 2.0
// Project 006 v2 - submit-order canonical -> Alpaca POST /v2/orders body.
//
// Input:  vars.normalized (produced upstream by the flow's Normalize step,
//         same shape as submit-order-request.dwl).
// Output: JSON matching Alpaca's orders endpoint contract:
//           {
//             symbol, qty, side, type, time_in_force,
//             limit_price  (only when type == "limit")
//           }
//
// Mapping:
//   canonical ticker      -> Alpaca symbol
//   canonical side        -> Alpaca side       (lowercased: "buy" | "sell")
//   canonical quantity    -> Alpaca qty        (sent as string per Alpaca docs)
//   canonical order_type  -> Alpaca type       (lowercased: "market" | "limit")
//   canonical limit_price -> Alpaca limit_price (only for LIMIT orders)
//   default time_in_force = "day"
output application/json
---
{
  symbol: vars.normalized.ticker,
  qty: vars.normalized.quantity as String,
  side: lower(vars.normalized.side),
  "type": lower(vars.normalized.order_type default "MARKET"),
  time_in_force: "day"
}
++ (
  // Include limit_price ONLY on LIMIT orders and only when provided.
  if (
    upper(vars.normalized.order_type default "MARKET") == "LIMIT"
    and vars.normalized.limit_price != null
  )
    { limit_price: vars.normalized.limit_price as String }
  else
    {}
)
