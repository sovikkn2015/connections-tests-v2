# V3-B Nginx Sidecar — Operations Runbook

Canonical implementation of Option C from
[docs/v3-b-infra-debug-findings.md](./v3-b-infra-debug-findings.md) —
the only path that unblocks `/sec-edgar/tools/list` without modifying V2.

## Why This Exists

The V2 API Gateway (`og256a1neb`) is **EDGE-optimized**, which means AWS
puts a managed CloudFront distribution in front of every invoke. CloudFront
dispatches to the right distribution based on the `Host` header. When Flex
Gateway's Envoy forwards a request, it preserves the incoming ALB hostname
as the Host header. CloudFront has no distribution for
`ir-flex-gateway-alb-...` and returns HTTP 400.

Flex Gateway's declarative YAML exposes neither Envoy's
`host_rewrite_literal` nor `auto_host_rewrite`. Its shipped policies
(`header-injection-flex`, `dataweave-headers-transformation-flex`) cannot
override Envoy's reserved pseudo-headers (`:authority` / `Host`). See the
infra-debug doc for the full trail of what we tried.

**The nginx sidecar bridges that gap**. Flex proxies to
`http://127.0.0.1:8082/…`; nginx rewrites Host + SNI to
`og256a1neb.execute-api.us-east-1.amazonaws.com`; CloudFront accepts the
request; APIGW authorizes via the `x-api-key` that Flex already injected.

## Architecture

```
 ┌─────────────────────────────────────────────────────────────────────┐
 │  ECS task: ir-flex-gateway-task  (awsvpc, shared netns)             │
 │                                                                     │
 │  ┌──────────────┐                                                   │
 │  │ config-sync  │  init container: s3 sync s3://…/v3-b/  → /shared  │
 │  │  (essential  │  (STOPPED exit 0)                                 │
 │  │   = false)   │                                                   │
 │  └──────────────┘                                                   │
 │                                                                     │
 │  ┌──────────────┐  dependsOn:                                       │
 │  │ flex-gateway │  • config-sync              SUCCESS               │
 │  │  :8081       │  • nginx-upstream-proxy     HEALTHY               │
 │  │              │                                                   │
 │  │  (Envoy;     │  Injects x-api-key via header-injection-flex      │
 │  │   routes all │  PolicyBinding; applies rate-limit + FINRA audit. │
 │  │   traffic to │                                                   │
 │  │   127.0.0.1: │  Upstream (api.yaml):                             │
 │  │   8082)      │     address: http://127.0.0.1:8082/               │
 │  └──────┬───────┘                                                   │
 │         │ http (loopback)                                           │
 │         ▼                                                           │
 │  ┌──────────────┐  Container healthcheck: wget /healthz             │
 │  │ nginx-       │  essential=true                                   │
 │  │ upstream-    │  portMappings=[]  (loopback only)                 │
 │  │ proxy  :8082 │                                                   │
 │  │              │  Rewrites:                                        │
 │  │  (nginx      │    • Host  → og256a1neb.execute-api…             │
 │  │   1.27       │    • SNI   → og256a1neb.execute-api…             │
 │  │   alpine)    │    • proxy_ssl_verify on + CA bundle              │
 │  └──────┬───────┘                                                   │
 └─────────┼───────────────────────────────────────────────────────────┘
           │ TLS 1.2/1.3, verified
           ▼
 ┌──────────────────────┐        ┌──────────────────────┐
 │  CloudFront          │  →     │  V2 API Gateway      │
 │  (EDGE managed)      │        │  og256a1neb  /prod   │
 │  routes by Host      │        │  Usage Plan checks   │
 │  header              │        │  x-api-key           │
 └──────────────────────┘        └──────────────────────┘
```

Traffic flow on a tool call:

1. Client → ALB (`http://ir-flex-gateway-alb-…/sec-edgar/tools/list`)
2. ALB → flex-gateway:8081 (Envoy; policies fire)
3. flex-gateway → 127.0.0.1:8082 (same task, loopback)
4. nginx → `https://og256a1neb.execute-api.us-east-1.amazonaws.com/prod/sec-edgar/tools/list`
   with Host + SNI rewritten, x-api-key preserved
5. CloudFront → V2 APIGW → Lambda

## What Nginx Rewrites and Does Not Rewrite

| Field                            | Action                                            |
| -------------------------------- | ------------------------------------------------- |
| `Host`                           | Rewrite to `og256a1neb.execute-api.us-east-1.amazonaws.com` |
| TLS SNI                          | Set to `og256a1neb.execute-api.us-east-1.amazonaws.com` |
| `proxy_ssl_verify`               | `on` with `/etc/ssl/certs/ca-certificates.crt`    |
| `x-api-key`                      | Forward verbatim (Flex injected it inbound)        |
| `x-agent-id`, `x-correlation-id` | Forward verbatim + emit to nginx access log       |
| `x-tool-name`                    | Forward verbatim + emit to nginx access log       |
| `X-Forwarded-For/Proto/Host`     | Chain-appended for APIGW access logs              |
| Request body                     | Passed through (client_max_body_size 10m)         |
| `/healthz`                       | Short-circuits with `200 ok` — does not call APIGW |

## Files

| File                                              | Purpose                          |
| ------------------------------------------------- | -------------------------------- |
| `aws/nginx-sidecar/nginx.conf`                    | Proxy config                     |
| `aws/nginx-sidecar/Dockerfile`                    | `FROM nginx:1.27-alpine` + CA     |
| `scripts/deploy-nginx-sidecar.sh`                 | End-to-end deploy pipeline       |
| `agent-fabric/flex-config/api.yaml`               | Upstream → `http://127.0.0.1:8082/` |
| `agent-fabric/.build-receipts/nginx-sidecar.json` | Latest deploy receipt            |

## How to Rotate the Image

```bash
# From the V3 agent fabric project root.
# Makes a new image tag, pushes, rolls the ECS service, re-verifies.
bash scripts/deploy-nginx-sidecar.sh
```

The script is idempotent. Re-running:
- reuses the existing ECR repo,
- tags a fresh `sha-<git>-<ts>` image + `:latest`,
- registers a new task-def revision,
- `force-new-deployment` so the service picks up the new revision,
- waits ≤5 min for `services-stable`,
- probes `/sec-edgar/tools/list` and `/sec-edgar/tools/call`,
- rewrites `agent-fabric/.build-receipts/nginx-sidecar.json`.

To change the nginx config only (no image rebuild), edit
`aws/nginx-sidecar/nginx.conf` and re-run the same script — Docker rebuilds
the layer, a new image is pushed, the task rolls.

## How to Roll Back

Two rollback scopes, from least to most invasive:

### A. Pin to a previous task-def revision (no rebuild)

```bash
aws ecs update-service --region us-east-1 \
    --cluster ir-flex-gateway-cluster \
    --service ir-flex-gateway-svc \
    --task-definition ir-flex-gateway-task:<OLD_REV> \
    --force-new-deployment
aws ecs wait services-stable --region us-east-1 \
    --cluster ir-flex-gateway-cluster --services ir-flex-gateway-svc
```

### B. Point Flex back at APIGW directly (known-broken but harmless)

1. Edit `agent-fabric/flex-config/api.yaml`:
   ```yaml
   spec:
     services:
       v2-apigw:
         address: https://og256a1neb.execute-api.us-east-1.amazonaws.com/prod/
   ```
2. Re-sync the bundle and force a deploy:
   ```bash
   bash scripts/apply-flex-config-v2.sh
   ```
3. The nginx sidecar keeps running (it's essential=true, so removing it
   requires a task-def revision). It's idle; no traffic reaches it.
4. Expected outcome: ALB probe returns 400 again (CloudFront Host
   mismatch). Use only if the sidecar itself is faulting.

To fully remove the sidecar, roll the service back to task-def `:5` (the
pre-sidecar revision) with the command in (A).

## Troubleshooting

### `/sec-edgar/tools/list` returns 400

- Confirm S3 bundle points Flex at `127.0.0.1:8082`:
  ```bash
  aws s3 cp s3://ir-flex-gateway-config-875460787302/v3-b/api.yaml - \
      --region us-east-1 | grep -A1 "v2-apigw:"
  ```
- Force Flex to reload by bouncing the service:
  ```bash
  aws ecs update-service --region us-east-1 \
      --cluster ir-flex-gateway-cluster --service ir-flex-gateway-svc \
      --force-new-deployment
  ```

### `/sec-edgar/tools/list` returns 502/504

This is nginx's signal that the upstream TLS failed. With
`proxy_ssl_verify on`, a missing CA bundle will cause this.

```bash
# Verify the CA bundle is in the image.
docker run --rm 875460787302.dkr.ecr.us-east-1.amazonaws.com/ir-flex-gateway-nginx:latest \
    ls -la /etc/ssl/certs/ca-certificates.crt
```

If missing, the Dockerfile's `apk add ca-certificates && update-ca-certificates`
didn't run. Rebuild.

### Nginx container unhealthy → flex-gateway stuck PENDING

`dependsOn: nginx-upstream-proxy condition=HEALTHY` gates flex startup.
If nginx fails its healthcheck (bad config, port conflict), flex never
starts. Check:

```bash
aws logs filter-log-events --region us-east-1 \
    --log-group-name /ecs/ir-flex-gateway \
    --log-stream-name-prefix nginx-upstream-proxy/ \
    --start-time $(($(date +%s)000 - 300000))
```

### Correlation IDs not appearing in nginx logs

Confirm the request hits nginx with the header by checking the nginx
access log format: look for `cid="..."` lines. If nginx never sees them,
the headers aren't reaching nginx — look at flex-gateway's logs for the
outbound request, and confirm `proxy_pass_request_headers on` is set in
`nginx.conf`.
