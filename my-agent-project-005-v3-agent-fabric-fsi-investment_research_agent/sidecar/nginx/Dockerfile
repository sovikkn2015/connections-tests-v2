# ─────────────────────────────────────────────────────────────────────────────
# nginx sidecar for V3-B Flex Gateway ECS task.
#
# Purpose:
#   Flex Gateway (Envoy) cannot rewrite the outbound Host header / SNI for
#   the V2 API Gateway upstream (og256a1neb), which is EDGE-optimized and
#   fronted by CloudFront. CloudFront returns 400 to any request whose Host
#   header isn't the API-Gateway hostname.
#
#   This container sits on localhost:8080 inside the task. Flex forwards
#   requests to http://127.0.0.1:8080/... and nginx rewrites Host + SNI to
#   og256a1neb.execute-api.us-east-1.amazonaws.com before proxying to the
#   real upstream.
#
# Runs on Fargate linux/amd64.
# ─────────────────────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine

# Remove stock default server, replace with our proxy config.
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/nginx.conf

# Flex → nginx happens on loopback; expose 8080 for clarity.
EXPOSE 8080

# nginx:alpine's default user/entrypoint is fine.
STOPSIGNAL SIGQUIT
CMD ["nginx", "-g", "daemon off;"]
