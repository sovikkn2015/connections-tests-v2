%dw 2.0
// Project 006 v3 - Alpaca order callback -> MCP tools/call payload.
//
// Calls the mulesoft-actions MCP server's order_status_webhook tool. The
// MCP contract (see aws/mcp-servers/mulesoft-actions/app.py) wants:
//   order_id, status, filled_quantity?, avg_fill_price?, timestamp
//
// Alpaca sends its own event shape; we translate.
output application/json
var o = payload.order default {}
---
{
  jsonrpc: "2.0",
  id: "webhook-" ++ (o.id default "unknown"),
  method: "tools/call",
  params: {
    name: "order_status_webhook",
    arguments: {
      order_id: o.id default "",
      status: (payload.event default o."status" default "new") as String,
      filled_quantity: if ((o.filled_qty default "") != "") (o.filled_qty as Number) else null,
      avg_fill_price: if ((o.filled_avg_price default "") != "") (o.filled_avg_price as Number) else null,
      timestamp: payload.timestamp default (now() as String)
    }
  }
}
