# ──────────────────────────────────────────────────────────────────────────
# MuleSoft Flex Gateway — container image for Project 005 V3 Agent Fabric
# ──────────────────────────────────────────────────────────────────────────
# NOTE: `:latest` is used during Phase 1 bring-up.
#       Production MUST pin to a specific tag (e.g. mulesoft/flex-gateway:1.8.0)
#       before cutover — see aws/flex-gateway/README.md § "Version pinning".
#
# The image is intentionally thin: it adds only
#   1. config mount points under /usr/local/share/mulesoft/flex-gateway/conf.d/
#   2. an entrypoint that fetches Anypoint creds from AWS Secrets Manager at
#      CONTAINER START (not at build time), registers via `flexctl`, then
#      execs the stock gateway binary.
# ──────────────────────────────────────────────────────────────────────────
FROM mulesoft/flex-gateway:latest

# Run as root only long enough to install deps + set perms, then drop back.
USER root

# awscli v2 for Secrets Manager retrieval; jq for JSON parsing.
# The base image is Red Hat UBI — use microdnf when available, yum otherwise.
RUN (command -v microdnf >/dev/null 2>&1 && microdnf install -y awscli jq && microdnf clean all) \
 || (command -v yum >/dev/null 2>&1 && yum install -y awscli jq && yum clean all) \
 || (command -v dnf >/dev/null 2>&1 && dnf install -y awscli jq && dnf clean all)

# Config + scripts mount points
RUN mkdir -p /usr/local/share/mulesoft/flex-gateway/conf.d/ \
 && mkdir -p /opt/flex-gateway/bin/

COPY flex-gateway-config.yaml /usr/local/share/mulesoft/flex-gateway/conf.d/flex-gateway-config.yaml
COPY registration.sh /opt/flex-gateway/bin/registration.sh
COPY entrypoint.sh   /opt/flex-gateway/bin/entrypoint.sh

RUN chmod +x /opt/flex-gateway/bin/registration.sh /opt/flex-gateway/bin/entrypoint.sh \
 && chown -R flex:flex /usr/local/share/mulesoft/flex-gateway/conf.d/ /opt/flex-gateway/bin/ 2>/dev/null || true

# Drop privileges — Flex Gateway's default runtime user
USER flex

# Listener (matches flex-gateway-config.yaml) + health
EXPOSE 8080

# Health probe — honored by ECS task and ALB target group
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/health || exit 1

ENTRYPOINT ["/opt/flex-gateway/bin/entrypoint.sh"]
