# market-data MCP server (V3)

Tools:
- `get_quote(symbol)` — real-time quote, 15s warm-cache
- `get_historical(symbol, period)` — daily OHLCV (1mo | 3mo | 6mo | 1y)
- `get_technicals(symbol)` — RSI-14, MACD, SMA-50/200, Bollinger

Backends:
- Primary: Finnhub (`FINNHUB_API_KEY`)
- Fallback: Alpha Vantage (`ALPHA_VANTAGE_API_KEY`)

Modes:
- `MARKET_DATA_MODE=live` — hit vendors
- `MARKET_DATA_MODE=mock` — deterministic fixtures (no creds)

MCP protocol:
- `GET /` → `{name, version, tools[]}`
- `POST /tools/list`
- `POST /tools/call` with header `X-MCP-API-Key`

Context headers consumed (forwarded to span):
`X-Principal-Id`, `X-Agent-Id`, `X-Persona`, `X-Session-Id`.
