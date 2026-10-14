#!/usr/bin/env bash
# ============================================================================
# warm-start.sh — Pre-demo warming. Fires one dummy query per persona so
# AgentCore, the WebSocket gateway, and the SF Auth Proxy are all warm by
# the time the panel walks in.
#
# Usage:  AGENTCORE_URL=wss://... SESSION_TOKEN=... ./scripts/warm-start.sh
# ============================================================================

set -euo pipefail

: "${AGENTCORE_URL:?AGENTCORE_URL env var required}"
: "${SESSION_TOKEN:?SESSION_TOKEN env var required (from IdP)}"

log() { printf "\033[1;34m[warm-start]\033[0m %s\n" "$*"; }

warm_persona() {
  local persona="$1" query="$2"
  log "warming ${persona}: ${query}"
  python3 - "${AGENTCORE_URL}" "${SESSION_TOKEN}" "${persona}" "${query}" <<'PY'
import asyncio, json, sys
import websockets

url, tok, persona, query = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

async def main():
    u = f"{url}?authorization=Bearer%20{tok}&x-persona={persona}"
    async with websockets.connect(u, close_timeout=5) as ws:
        await ws.send(json.dumps({"type": "turn", "turn_id": "warm", "text": query}))
        try:
            for _ in range(10):
                await asyncio.wait_for(ws.recv(), timeout=0.3)
        except asyncio.TimeoutError:
            pass
        print("warmed")

asyncio.run(main())
PY
}

warm_persona fsi_research "ping"
warm_persona fsi_advisor "ping"
warm_persona fsi_client_liaison "ping"

log "All three personas warm."
