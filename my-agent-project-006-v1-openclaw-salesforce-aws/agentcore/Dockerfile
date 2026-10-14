# AgentCore container: Official OpenClaw image + HTTP REST adapter
# Uses the official OpenClaw Docker image as base (reproducible, tested).
# Adapter on :8080 bridges AgentCore HTTP to OpenClaw Gateway REST API.
#
# Architecture: adapter calls Gateway REST API (POST /v1/chat/completions)
# with /hooks/agent fallback — simpler, no ws library needed.

FROM ghcr.io/openclaw/openclaw:latest AS base

USER root

# Fix plugin ownership (OpenClaw 2026.4.21 blocks uid=1000 plugins)
RUN chown -R root:root /app/extensions && chmod -R u+rwX /app/extensions

# ── Install adapter dependencies (express only) ──
WORKDIR /adapter
COPY adapter-package.json ./package.json
RUN npm install --omit=dev

# ── Copy adapter and startup ──
COPY adapter.js ./
COPY start.sh ./
RUN chmod +x start.sh

# ── Copy OpenClaw config ──
COPY openclaw.json /app/openclaw.json
COPY mcp-rest-bridge.mjs /adapter/mcp-rest-bridge.mjs

# ── Seed workspace bootstrap files so OpenClaw does not inject "missing file"
#    markers. Identity/rules come from systemPromptOverride; these stubs just
#    satisfy OpenClaw's bootstrap ritual so no preamble leaks into responses.
COPY AGENTS.md    /app/AGENTS.md
COPY IDENTITY.md  /app/IDENTITY.md
COPY TOOLS.md     /app/TOOLS.md
RUN printf '%s\n' '# SOUL' 'Professional FSI equity research analyst. Direct, factual, tool-grounded. No persona header, no vibe, no emoji, no preamble.' > /app/SOUL.md \
 && printf '%s\n' '# USER' 'Session user identity is provided by the gateway. No onboarding or identity dialogue.' > /app/USER.md \
 && printf '%s\n' '# Ready' 'Agent is configured. Answer the user query directly.' > /app/BOOTSTRAP.md \
 && chown root:root /app/AGENTS.md /app/IDENTITY.md /app/TOOLS.md /app/SOUL.md /app/USER.md /app/BOOTSTRAP.md

WORKDIR /app

EXPOSE 8080 18789

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8080/ping || exit 1

CMD ["/adapter/start.sh"]
