# 007 Foundation — Module-Aligned CloudFormation

One stack per 007 module, not one big monolith.

## Why module-aligned (not service-grouped)

A 2023-mindset IaC repo groups by AWS service: one `dynamodb.yaml` for every
table, one `s3.yaml` for every bucket, one `iam.yaml` for every role.

That pattern breaks for 007 because:

1. **Blast radius.** Changing an M1 table redeploys a stack that also holds
   M10's audit table. Cross-module outages.
2. **Ownership.** The trust-layer team owns M1+M2/M4+M6+M10. The
   intelligence-layer team owns M8+specialists. They need independent
   deploys with their own change windows.
3. **Retention.** M10's WORM bucket and audit DDB must outlive M8 rewrites.
   `DeletionPolicy: Retain` per-resource is insufficient — whole stacks
   should be scoped so that a clean `cloudformation delete-stack` of M8
   can never touch M10.
4. **Cross-module contract.** Rule 9 says modules communicate via REST/MCP
   only. That rule applies to CloudFormation too: modules expose their
   ARNs via `!Export`, consumers use `!ImportValue`. No direct `Ref`
   across modules.

## Structure

```
cloudformation/
├── platform-common.yaml        # KMS key, CFN staging bucket, shared base
├── m1-identity.yaml            # AID registry DDB + JWT keypair secret
├── m10-audit-logger.yaml       # Audit DDB + S3 WORM + DLQ SQS (all Retain)
├── m8-pipeline-engine.yaml     # LangGraph checkpoint DDB
├── m13-fix-bridge.yaml         # FIX session DDB + counterparty credentials
├── execution-specialist.yaml   # Execution orders DDB
├── onboarding-specialist.yaml  # Onboarding sessions DDB
├── memory-service.yaml         # Memory L2 (TTL) + L3 DDB
├── irsa.yaml                   # 7 IAM roles, one per module SA
└── deploy.sh                   # strict order: platform -> modules (parallel) -> irsa
```

## Deploy

```bash
export AWS_REGION=us-east-1
export PREFIX=fsi007cf
export ENVIRONMENT=dev
export EKS_OIDC_PROVIDER_ARN=arn:aws:iam::123456789012:oidc-provider/...  # optional

./deploy.sh
```

Idempotent. Re-running with no changes produces no events.

## Destroy

```bash
# Reverse order: irsa -> modules -> platform-common
aws cloudformation delete-stack --stack-name 007-dev-irsa
for m in m1-identity m10-audit-logger m8-pipeline-engine m13-fix-bridge \
         execution-specialist onboarding-specialist memory-service; do
  aws cloudformation delete-stack --stack-name 007-dev-$m
done
aws cloudformation delete-stack --stack-name 007-dev-platform-common
```

Even after delete:
- **M10 WORM bucket stays.** `DeletionPolicy: Retain` + S3 Object Lock
  Compliance mode guarantees 6-year retention of every audit record.
- **M10 audit DDB stays.** Same rationale.
- **M1 JWT keypair secret stays.** Key rotation must be explicit.
- Everything else (pay-per-request DDB, KMS alias) tears down cleanly.

## Cross-module contract (exports)

Every module exports its resource ARNs under the naming convention:

```
007-<module-name>-<ResourceName>
```

Examples:
- `007-m1-identity-AidRegistryTableArn`
- `007-m10-audit-logger-AuditWormBucketArn`
- `007-platform-KmsKeyArn`

Consumers use `!ImportValue '007-m1-identity-AidRegistryTableArn'`. Only the
IRSA stack and the platform shared bits consume these; business modules
never import from each other (same rule as the runtime REST contract).

## Mapping to the 007 architecture

| 007 Module            | CF Stack                | Stack Owner       |
|-----------------------|-------------------------|-------------------|
| (shared)              | `platform-common`       | platform team     |
| M1 Agent Identity     | `m1-identity`           | trust-layer team  |
| M10 Audit Logger      | `m10-audit-logger`      | trust-layer team  |
| M8 Pipeline Engine    | `m8-pipeline-engine`    | intelligence team |
| M13 FIX Bridge        | `m13-fix-bridge`        | tier-2/5 team     |
| Execution Specialist  | `execution-specialist`  | intelligence team |
| Onboarding Specialist | `onboarding-specialist` | intelligence team |
| Memory Service        | `memory-service`        | intelligence team |
| (cross-cutting IAM)   | `irsa`                  | platform team     |

Modules not in AWS (M2/M4 OPA, M3 schema, M5 config, M6 gateway, M7
translators, M9 intent router, M11 adapters, M12 agent runtime): these
are stateless services with no AWS resources of their own. Their
Helm chart references the Bedrock IAM role via IRSA if they need LLM
access. Everything they store lives in another module's stack.

## Why parallel for step 2

None of the per-module stacks reference another module via `!ImportValue`.
They only reference `platform-common`. So they can be created
concurrently after platform-common is done. The `deploy.sh` runs them in
background subshells and `wait`s.
