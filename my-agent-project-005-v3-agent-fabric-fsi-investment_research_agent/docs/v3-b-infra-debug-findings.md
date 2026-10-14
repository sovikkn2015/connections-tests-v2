# V3-B Flex Gateway Infrastructure Debug Findings

**Date:** 2026-04-26
**Scope:** Debug why the V3-B Flex Gateway on AWS ECS returns non-2xx for
`/sec-edgar/tools/list` via the ALB.
**Status:** Gateway is fully booted. 503 (registration missing) is
**resolved**. 400 (upstream Host/CloudFront) is the remaining blocker
and is architectural — see "Next Steps" for the minimum-cost fix path.

## TL;DR

The Flex Gateway container is healthy, reads config correctly, parses
our ApiInstance + all PolicyBindings, runs Envoy, binds 8081, and the
ALB target shows `State: healthy`. Requests hit Envoy, fire the
rate-limit and message-logging policies, and are then forwarded to the
V2 API Gateway upstream. The upstream is an **EDGE-optimized API
Gateway** fronted by CloudFront. CloudFront returns **HTTP 400** to
every Flex-proxied request because the outgoing `Host` header is still
the ALB hostname (`ir-flex-gateway-alb-...`), not the API Gateway
hostname (`og256a1neb.execute-api.us-east-1.amazonaws.com`) that
CloudFront expects.

Flex Gateway's available policies (`header-injection-flex`,
`dataweave-headers-transformation-flex`) cannot rewrite
`Host`/`:authority` — Envoy treats these as reserved pseudo-headers
and the ext_proc filter short-circuits (`Processing mode set to:
NONE`) when our DataWeave script tries to set them.

## What's Working (verified end-to-end)

| Check                                     | Evidence |
| ----------------------------------------- | -------- |
| ECS task RUNNING                          | `describe-tasks` → `lastStatus=RUNNING`, both containers healthy |
| `config-sync` downloads all 4 S3 files    | CloudWatch log: `download: s3://.../v3-b/registration.yaml to ../shared/registration.yaml` |
| Flex reads custom config                  | Log: `Reading config file '/etc/mulesoft/flex-gateway/conf.d/custom/api.yaml'` |
| Registration parsed                       | Log: `/Configuration/registration Added`, `/Secret/flex-registration Added` |
| ApiInstance parsed                        | Log: `/ApiInstance/fsi-mcp-servers Added` |
| PolicyBindings parsed                     | Log: `/PolicyBinding/finra-audit-binding Added`, `/PolicyBinding/rate-limit-binding Added`, `/PolicyBinding/v2-api-key-injection Added` |
| Envoy cluster built for upstream          | Log: `Adding Service default/fsi-mcp-servers-v2-apigw https://og256a1neb.execute-api.us-east-1.amazonaws.com:443/prod/` |
| Envoy listens on 0.0.0.0:8081             | ALB target state = `healthy` (health check on `/` passes with 200-499 matcher) |
| Policies fire on every request            | Log: `[policy: rate-limit-binding.default]` `Portion requested: 25, given: 25` |
| x-api-key injection is active             | Log: `Deserialized ... HeaderInjectionConfig ... name: "x-api-key" ... value: <live secret>` |

## What's NOT Working

| Symptom             | Evidence |
| ------------------- | -------- |
| ALB probe returns 400 | `curl http://ir-flex-gateway-alb-.../sec-edgar/tools/list` → `HTTP/1.1 400`, body empty |
| Response attribution  | Headers: `server: Anypoint Flex Gateway`, `x-cache: Error from cloudfront`, `via: ... cloudfront.net`, `x-amz-cf-pop: IAD61-P3` — confirms CloudFront returned the 400 and Flex passed it through |
| Host rewrite blocked  | `[flex-external-processor][debug] HeaderTransformationRequestHandler Processing mode set to: NONE` — ext_proc declined to modify request headers when `host` was in the script output |

## Root Cause

1. V2 API Gateway `og256a1neb` is configured with `endpointConfiguration.types: [EDGE]`.
2. EDGE-optimized API Gateway puts a managed CloudFront distribution in
   front of each API's invoke URL.
3. CloudFront routes to the right distribution based on the `Host` header.
4. Envoy-based Flex Gateway forwards the incoming request's `Host` header
   verbatim unless the route configuration sets `host_rewrite_literal`
   or `auto_host_rewrite` on the cluster.
5. Flex Gateway's declarative YAML does not expose either of those
   Envoy fields. Nor do its shipped policies (wasm header-injection,
   DataWeave headers transformation) successfully override `Host` —
   the ext_proc filter drops the mutation (Envoy reserved-header list).
6. Result: every Flex → upstream request arrives at CloudFront with
   `Host: ir-flex-gateway-alb-1565333524.us-east-1.elb.amazonaws.com`,
   CloudFront has no distribution for that host, returns 400.

## What We Tried That Didn't Work

1. Plain `header-injection-flex` with `Host` in `inboundHeaders`.
   Policy deserialized successfully (confirmed in logs) but the Envoy
   wasm filter for header-injection respects Envoy's reserved-header
   list; Host was not rewritten. Result: 400.
2. `dataweave-headers-transformation-flex` with `requestFlow: onRequest`
   and a DW script that outputs `host: "og256a1neb..."`. Policy loaded,
   script ran, but the ext_proc layer logged
   `Processing mode set to: NONE` and the request continued with the
   original Host. Result: 400.
3. Sending `Host: og256a1neb...` from the client. ALB strips and
   rewrites the Host header before it reaches Envoy. Result: 400.

## What We Kept (because it IS needed and works)

1. `api.yaml` with the named-service routing model
   (`spec.services.v2-apigw.address: https://...`) so Envoy builds a
   clean upstream cluster with correct SNI. This is the Mulesoft-
   documented pattern and Envoy's cluster logs confirm SNI is set to
   `og256a1neb.execute-api.us-east-1.amazonaws.com`.
2. `policy-header-injection.yaml` PolicyBinding (`header-injection-flex`)
   that injects the V2 MCP `x-api-key`. Confirmed in logs. This IS
   needed — when the Host issue is fixed, the upstream will still
   require `x-api-key` to pass the API Key Usage Plan check.
3. `registration.yaml` — the `flexctl registration create --mode local`
   bootstrap file.
4. `apply-flex-config-v2.sh` — idempotent, renders the x-api-key value
   from AWS API Gateway at apply time (never commits it).

## Next Steps (ordered by cost, cheapest first)

### Option A — Add a Regional Custom Domain to V2 API Gateway (cheapest, cleanest)

Cost: 1 ACM certificate (free) + 1 API Gateway custom domain
(~$0.15/day) + 1 Route 53 hosted zone entry (if using a new subdomain)
+ ~10 minutes of config work.

What it does: creates a `mcp.<yourdomain>` regional custom domain with
base-path mapping to the existing V2 API Gateway's prod stage. Regional
endpoint has no CloudFront in front; it accepts any Host header. V3
Flex Gateway points at `https://mcp.<yourdomain>/` — upstream works
immediately.

Doesn't modify V2: the existing EDGE-optimized invoke URL still works
for V2 consumers. We're adding a parallel regional alias.

Commands to run (high-level):

```bash
aws acm request-certificate \
    --domain-name mcp.<YOURDOMAIN> \
    --validation-method DNS \
    --region us-east-1

# Validate DNS record, wait for ISSUED, then:
aws apigateway create-domain-name \
    --domain-name mcp.<YOURDOMAIN> \
    --regional-certificate-arn <cert-arn> \
    --endpoint-configuration types=REGIONAL \
    --region us-east-1

aws apigateway create-base-path-mapping \
    --domain-name mcp.<YOURDOMAIN> \
    --rest-api-id og256a1neb \
    --stage prod \
    --region us-east-1

# Route 53: create an A ALIAS from mcp.<YOURDOMAIN> -> regional domain.

# Finally, flip V3-B config:
#   flex-config/api.yaml -> spec.services.v2-apigw.address: https://mcp.<YOURDOMAIN>/
bash scripts/apply-flex-config-v2.sh
```

### Option B — Replace V2 API Gateway endpoint type (cheapest but touches V2)

Changing `endpointConfiguration.types` from `EDGE` to `REGIONAL` on
`og256a1neb` removes CloudFront from the path.

User constraint says "don't modify V2 API Gateway" — skip.

### Option C — Put an Nginx sidecar in the ECS task that rewrites Host

Add a second container to `ir-flex-gateway-task` that listens on an
internal loopback port, receives from Envoy, rewrites
`Host: og256a1neb.execute-api.us-east-1.amazonaws.com`, and forwards
to the real upstream. Flex's `services.<name>.address` then points at
`http://127.0.0.1:<nginx-port>/`.

Cost: ~50 lines of task-definition JSON + a tiny nginx.conf. No AWS
resources added. Fully inside the V3 boundary.

Downside: adds an extra hop, extra container to monitor, and loses the
end-to-end TLS chain from Envoy to the upstream (Nginx would re-TLS).

### Option D — Build a custom Flex Gateway policy (highest cost, most flexible)

Mulesoft's PDK lets us compile a custom wasm policy that calls
`add_request_header` (or the pseudo-header equivalent). A custom policy
can set `:authority` at the Envoy wasm layer without going through
ext_proc.

Cost: 2-5 days of Rust/Go work + PDK learning curve + publishing the
policy into our own policy directory.

Recommendation: only pursue if Options A and C are both off the table.

## Recommendation

Go with Option A (regional custom domain). It's the minimum-cost, most
architecturally clean path, doesn't modify V2 behavior, and keeps V3-B
free of any custom code or extra sidecars. Once the custom domain is
live, change one line in `flex-config/api.yaml` and rerun
`apply-flex-config-v2.sh`.

## Artefacts

- `flex-config/api.yaml` — named-service ApiInstance pointing at V2 API Gateway.
- `flex-config/policy-header-injection.yaml` — injects V2 `x-api-key` (placeholder-rendered at apply time).
- `flex-config/policy-message-logging.yaml`, `flex-config/policy-rate-limit.yaml` — FINRA audit + rate limit.
- `flex-config/registration.yaml` — Flex Gateway bootstrap registration.
- `scripts/apply-flex-config-v2.sh` — idempotent config push; reads x-api-key from API Gateway at render time.
- `agent-fabric/.build-receipts/infra-debug.json` — this run's receipt.
