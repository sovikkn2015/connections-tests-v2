%dw 2.0
// Project 006 v3 - submit-order canonical -> Alpaca POST /v2/orders body.
//
// Input:  vars.normalized (produced by the flow's Normalize step).
// Output: JSON matching Alpaca's orders endpoint contract:
//           { symbol, qty, side, type, time_in_force, limit_price? }
//
// V3 change: canonical side is already lowercase ("buy"/"sell"), matches
// Alpaca's contract verbatim - no case conversion needed.
output application/json
---
{
  symbol: vars.normalized.ticker,
  qty: vars.normalized.quantity as String,
  side: vars.normalized.side,
  "type": vars.normalized.order_type default "market",
  time_in_force: "day"
}
++ (
  if (
    (vars.normalized.order_type default "market") == "limit"
    and vars.normalized.limit_price != null
  )
    { limit_price: vars.normalized.limit_price as String }
  else
    {}
)
