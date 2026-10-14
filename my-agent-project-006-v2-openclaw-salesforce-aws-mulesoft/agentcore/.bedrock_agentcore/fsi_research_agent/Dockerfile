# AgentCore container: OpenClaw Gateway + HTTP↔WS adapter
# Multi-stage build: node:22-slim base, OpenClaw installed, adapter on :8080

FROM node:22-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Install OpenClaw globally ──
RUN npm install -g openclaw

# ── Install adapter dependencies ──
COPY adapter-package.json ./package.json
RUN npm install --omit=dev

# ── Copy adapter and startup ──
COPY adapter.js ./
COPY start.sh ./
RUN chmod +x start.sh

# ── Copy OpenClaw config ──
# For production: CI/CD copies openclaw.json + mcp-rest-bridge.mjs into build context.
# For local: docker-compose mounts or pre-copies these files.
COPY openclaw.json ./openclaw.json
COPY mcp-rest-bridge.mjs ./mcp-rest-bridge.mjs

EXPOSE 8080 18789

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8080/ping || exit 1

CMD ["./start.sh"]
