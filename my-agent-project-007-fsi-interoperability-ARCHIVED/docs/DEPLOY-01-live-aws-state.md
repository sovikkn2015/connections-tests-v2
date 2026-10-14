# DEPLOY-01: Live AWS State — 007 Platform

> Date: April 18, 2026
> Account: 875460787302
> Region: us-east-1
> Prefix: `fsi007cf-`  (CloudFormation-managed) and `fsi007-` (earlier imperative, kept)

---

## What exists in AWS right now

### CloudFormation stacks (8, all `CREATE_COMPLETE`)

Deployed twice — second deploy reported `No changes to deploy` on every stack, proving idempotence.

| Stack                                  | Owner              | Resources                                    |
|----------------------------------------|--------------------|----------------------------------------------|
| `fsi007cf-dev-platform-common`         | platform team      | KMS key + CFN staging bucket                 |
| `fsi007cf-dev-m1-identity`             | trust-layer team   | AID registry DDB + JWT keypair secret        |
| `fsi007cf-dev-m8-pipeline-engine`      | intelligence team  | LangGraph checkpoint DDB                     |
| `fsi007cf-dev-m10-audit-logger`        | trust-layer team   | audit DDB + S3 WORM + SQS DLQ (all Retain)   |
| `fsi007cf-dev-m13-fix-bridge`          | tier-2/5 team      | FIX session DDB + counterparty secret        |
| `fsi007cf-dev-execution-specialist`    | intelligence team  | execution orders DDB                         |
| `fsi007cf-dev-onboarding-specialist`   | intelligence team  | onboarding sessions DDB                      |
| `fsi007cf-dev-memory-service`          | intelligence team  | memory L2 (TTL) + L3 DDB                     |

M2/M4 (OPA policy engine) and M6 (MCP gateway) have no AWS resources — they are stateless services deployed via Helm. Their CloudFormation footprint is zero by design.

IRSA stack (`fsi007cf-dev-irsa`) is defined in `infra/aws/cloudformation/irsa.yaml` but not yet deployed — it needs `EKS_OIDC_PROVIDER_ARN` and `EKS_OIDC_ISSUER` supplied when an EKS cluster is available.

### Cross-stack exports

25 under the `007-<module>-<ResourceName>` naming contract. List them with:

```bash
aws cloudformation list-exports --region us-east-1 \
  --query "Exports[?starts_with(Name, '007-')].[Name,Value]" --output table
```

Examples:

- `007-m1-identity-AidRegistryTableArn`
- `007-m10-audit-logger-AuditWormBucketArn`
- `007-platform-KmsKeyArn`

The IRSA stack consumes these via `ImportValue` — same contract as the runtime REST/MCP boundary (modules communicate only via published interfaces, never via direct reference).

### DynamoDB (8 tables)

All pay-per-request, PITR on, KMS-SSE with the platform key.

- `fsi007cf-dev-m1-aid-registry`
- `fsi007cf-dev-m10-audit-log`
- `fsi007cf-dev-m8-pipeline-ckpt`
- `fsi007cf-dev-m13-fix-sessions`
- `fsi007cf-dev-execution-orders`
- `fsi007cf-dev-onboarding`
- `fsi007cf-dev-memory-l2`  (TTL on `ttl` attribute)
- `fsi007cf-dev-memory-l3`

### S3 buckets (CloudFormation-managed)

- `fsi007cf-dev-m10-audit-worm-us-east-1` — Object Lock **Compliance** mode, 6-year default retention (SEC 17a-4), KMS-encrypted, HTTPS-only policy, `DeletionPolicy: Retain`
- `fsi007cf-dev-cfn-staging-us-east-1`    — template staging (30-day lifecycle)

### S3 audit records (from the live end-to-end run)

- Bucket: `fsi007-audit-worm-us-east-1` (pre-CF imperative bucket, intentionally retained for evidence)
- 228 WORM-protected JSON audit objects
- Path: `acme_wm/audit/YYYY/MM/<uuid>.json`
- Earliest: 11:02:25, latest: 11:09:49 (all written today by `scripts/live_e2e_bedrock.py`)

### SQS queues

- `fsi007cf-dev-m10-audit-dlq` (with its own dead-letter)
- `fsi007cf-dev-m10-audit-dlq-deadletter`

Both KMS-encrypted, 14-day retention, max 5 receive attempts before terminal DLQ.

### KMS

- `alias/fsi007cf-dev-platform` — key rotation enabled, used by every module's at-rest encryption (DDB SSE, Secrets Manager, S3 SSE, SQS SSE)

### Secrets Manager (created empty per Rule 20)

- `fsi007cf/dev/m1/jwt-keypair`               — M1 RSA-2048 for JWT RS256
- `fsi007cf/dev/m13/counterparty-credentials` — FIX Logon username/password

Populated out-of-band (Vault / AWS Secrets Manager operator), never in CloudFormation parameters.

### IAM (not yet deployed)

`irsa.yaml` defines 7 least-privilege roles scoped per-module. Each trust policy locks a single K8s ServiceAccount to the module's own published resource ARNs via `ImportValue`. Deploys when EKS OIDC parameters are supplied.

---

## Repository state

- GitHub: `sovikkn2015/connections-tests`
- Branch: `main`
- HEAD: `c4606f9`
- Source files in 007 project: 363

### Most recent 10 commits

```
c4606f9  007: M9 v2 Strands router + wedge Helm chart + perf test + misc
b69b89c  007: module-aligned CloudFormation (one stack per 007 module)
d1cc870  007: LIVE END-TO-END PROOF — Strands + Bedrock + M6 trust + real AWS
54bff3e  007: Scalability, accuracy, stress testing — honest assessment doc
391b88f  007: Replace ALL in-memory mockeries with real database backends
4ed1def  feat: wire 004 and 005 to real Agentforce Agent API via ECA token
b3e6a92  007: BUILD AGENTIC CORE — Strands SDK supervisor + 5 specialists
5ec0447  007: ARCH-10 decisions approved — dual versions, Gateway behind M6
7b3d476  007: ARCH-10 — Agentic core redesign. Strands SDK + AgentCore.
aa36dcf  007: REV-11 — The Empty Room. 91K lines, zero LLM calls.
```

---

## How to verify any of it yourself

```bash
# 1. See every CF stack
aws cloudformation list-stacks --region us-east-1 \
  --stack-status-filter CREATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName, 'fsi007cf-')].[StackName]" --output text

# 2. Inspect a specific module's resources
aws cloudformation describe-stack-resources \
  --region us-east-1 --stack-name fsi007cf-dev-m10-audit-logger

# 3. Look at an audit record from the live test
aws s3 cp \
  s3://fsi007-audit-worm-us-east-1/acme_wm/audit/2026/04/033f94ef-261b-43cc-adaa-214a710230f4.json -

# 4. Re-run the live end-to-end (agent, Bedrock, trust pipeline, audit)
cd my-agent-project-007-fsi-interoperability
python3 scripts/live_e2e_bedrock.py

# 5. Re-run the M9 v2 classifier smoke test
python3 scripts/smoke_m9_v2.py

# 6. Re-deploy the CF stacks (idempotent — no changes on clean state)
./infra/aws/cloudformation/deploy.sh

# 7. Open the repo on GitHub
open https://github.com/sovikkn2015/connections-tests/tree/main/my-agent-project-007-fsi-interoperability
```

---

## What's NOT deployed (honest)

- **EKS cluster** — no cluster yet, so the IRSA stack and the Helm charts (`007-wedge`, `007-platform`) are not running. Charts and CF are ready; cluster provisioning is a separate one-time setup.
- **M6 / M2-M4 / M11 adapters as live services** — stateless services run from Helm; not visible in CF because CF only tracks AWS resources. They were proven live in-process during `scripts/live_e2e_bedrock.py` (5 uvicorn subprocesses + real Bedrock + real S3 WORM writes).
- **Production OPA policy bundle S3 hosting** — OPA in the wedge chart bundle-fetches from an S3 URL; bundle upload is a separate CI step, not part of these CF stacks.
- **Customer data** — zero. All test data is synthetic (`CLT-0042` = "Henderson Family Trust", `VOO` + `AGG` holdings).

---

*DEPLOY-01 — Project 007 FSI Interoperability Platform*
*What's on disk, what's in git, what's in AWS — one document, all verifiable.*
