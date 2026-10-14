# 007 Wedge Helm Chart — "Compliance Proxy for MCP"

Ships the 007 trust layer (M1 + M2/M4 + M6 + M10) as a single Helm release.

Sits between any MCP client and any MCP server. Every call is:
- **M1 identity-verified** (JWT RS256 + FSI claims)
- **M2/M4 authority-checked** (OPA/Rego, 2,100+ rules, deterministic)
- **M4 MNPI-filtered** (per-field, by archetype + role + jurisdiction)
- **M10 3-tier WORM-audited** (Langfuse + S3 Object Lock + CRM, SHA-256)

## Prereqs

- EKS cluster (or any k8s with ALB controller + cert-manager)
- AWS resources provisioned via `infra/aws/provision_007_aws.sh`:
  - S3 bucket with Object Lock (Compliance mode, 6yr retention)
  - SQS queue (audit DLQ)
- IRSA role bound to audit writes + bedrock access
- Kubernetes Secret `m1-rsa-keys` with `private.pem` + `public.pem`

## Install

```bash
# Generate RSA keys (one-time, store in Secrets Manager for real deployments)
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
kubectl create secret generic m1-rsa-keys \
    --from-file=private.pem --from-file=public.pem

# Install
helm install 007-wedge ./infra/helm/007-wedge \
    --set global.archetype=tier4_independent_ria \
    --set global.firmId=acme-wm \
    --set m10.env.M10_S3_BUCKET=fsi007-audit-worm-us-east-1 \
    --set m10.env.M10_DLQ_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/875460787302/fsi007-audit-dlq
```

## Verify

```bash
# Wait for rollout
kubectl rollout status deploy/007-wedge-m1-identity
kubectl rollout status deploy/007-wedge-m2-m4-policy
kubectl rollout status deploy/007-wedge-m10-audit-logger
kubectl rollout status deploy/007-wedge-m6-gateway

# Smoke via M6 health
kubectl port-forward svc/007-wedge-m6-gateway 8006:8006 &
curl -s localhost:8006/health | jq

# End-to-end: run scripts/live_e2e_bedrock.py against this cluster
M6_GATEWAY_URL=http://localhost:8006 python3 scripts/live_e2e_bedrock.py
```

## Pricing (ballpark)

| Line item                                  | Cost        |
|--------------------------------------------|-------------|
| EKS control plane                          | $73/mo      |
| 3x c6g.large worker nodes                  | $180/mo     |
| ALB                                        | $22/mo      |
| S3 + Object Lock (100k audit objects/mo)   | ~$5/mo      |
| DynamoDB (pay-per-request, AID+audit)      | ~$5/mo      |
| SQS (negligible)                           | <$1/mo      |
| Total (RIA customer, Tier 4)               | ~$285/mo    |

Sell it at $500-$2,000/mo per RIA (per 007 consolidated design).
Gross margin: 85%+.

## What the wedge DOES NOT include

- M3 canonical schema  — not needed for compliance proxy
- M7 translators       — not needed if customer brings their own MCP servers
- M8 pipeline engine   — no research loop in wedge
- M9 intent router     — no NL intent in wedge
- M11 adapters         — customer supplies their own MCP servers
- M12 web console      — optional, separate chart
- M13 FIX bridge       — not needed until Tier 2/5 (Phase 4)
- Smarsh archiving     — not needed for RIAs; required for BDs (Phase 3)
- 5 specialist agents  — wedge is a proxy, not a multi-agent system

Upgrade to full 007 platform via `infra/helm/007-platform` when customer
is ready for intelligence + adapters.
