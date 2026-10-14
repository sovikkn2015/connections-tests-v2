# V3 OpenClaw runtime — single Docker image, AgentCore deployment,
# three persona entry configs selected at session-open by X-Persona header.
# Base: Python 3.11 slim. No credentials baked in.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Copy the openclaw package (includes orchestration/, trust/, agents/ YAMLs,
# and the top-level coordinator shim).
COPY openclaw/ /app/openclaw/

# Non-root runtime user; AgentCore tolerates this.
RUN useradd --create-home --shell /bin/bash --uid 10001 runtime \
 && chown -R runtime:runtime /app
USER runtime

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8080/ping || exit 1

CMD ["python", "-m", "openclaw.agentcore_server"]
