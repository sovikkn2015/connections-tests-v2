# ─────────────────────────────────────────────────────────────────────────────
# nginx sidecar for V3-B Flex Gateway ECS task (canonical spec: Option C).
#
# Purpose:
#   Flex Gateway (Envoy) cannot rewrite the outbound Host header / SNI for
#   the V2 API Gateway upstream (og256a1neb), which is EDGE-optimized and
#   fronted by CloudFront. CloudFront returns 400 to any request whose
#   Host header is not the APIGW hostname.
#
#   This sidecar listens on 127.0.0.1:8082 inside the task's network
#   namespace. Flex forwards requests to http://127.0.0.1:8082/... and
#   nginx rewrites Host + SNI to og256a1neb.execute-api.us-east-1.amazonaws.com
#   before proxying to the real upstream with strict TLS verification.
#
# Runs on Fargate linux/amd64.
# ─────────────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# CA trust bundle required for proxy_ssl_verify on.
RUN apk add --no-cache ca-certificates wget \
    && update-ca-certificates \
    && rm -f /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/nginx.conf

# Loopback-only port — exposed for documentation; no host port mapping
# is created in the ECS task definition.
EXPOSE 8082

# ECS reads this healthcheck as containers[].healthStatus, which the
# flex-gateway container's dependsOn uses to gate startup.
HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1:8082/healthz || exit 1

STOPSIGNAL SIGQUIT
CMD ["nginx", "-g", "daemon off;"]
