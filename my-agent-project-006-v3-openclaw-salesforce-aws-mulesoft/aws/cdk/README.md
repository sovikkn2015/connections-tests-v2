# AWS CDK Stack — V3

Provisions the hybrid-cloud data layer infrastructure for V3: Aurora PostgreSQL with pgvector, Bedrock Knowledge Base with OpenSearch Serverless, EventBridge schedule for EDGAR ingestion, SQS for Salesforce CDC, and least-privilege IAM.

## Stacks

| Stack | What it creates |
|---|---|
| `VpcStack` | VPC with 2 AZs, 2 private + 2 public subnets, NAT gateway, Secrets Manager + SSM interface endpoints |
| `AuroraPgVectorStack` | Aurora PostgreSQL Serverless v2 (min 0.5 ACU, max 2 ACU), pgvector extension enabled via init script |
| `BedrockKnowledgeBaseStack` | Bedrock KB + OpenSearch Serverless collection + S3 ingestion bucket + IAM service role |
| `FilingsPipelineStack` | EDGAR ingestion Lambda + EventBridge schedule + DynamoDB dedup + S3 drag-drop bucket + Textract integration |
| `ResearchPipelineStack` | CDC Lambda + SQS queue + DLQ + EventBridge Partner Event source mapping for Salesforce |

## Deploy

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# one-time
cdk bootstrap aws://${AWS_ACCOUNT_ID}/us-east-1

# stage
cdk synth --all

# ship (in dependency order, bundled)
cdk deploy --all --require-approval never
```

## Environment the stacks consume

Most configuration is resolved at synth time from the context in `cdk.json` and `app.py`. Two env vars matter:

| Env var | Purpose |
|---|---|
| `CDK_DEFAULT_ACCOUNT` | AWS account id (usually set by the CLI) |
| `CDK_DEFAULT_REGION` | `us-east-1` for V3 |

The SEC User-Agent + Salesforce creds live in Secrets Manager and are referenced by ARN from the stacks; they are not populated by CDK.

## Outputs

After `cdk deploy`, the stacks emit:

- `AuroraEndpoint` — Aurora writer endpoint hostname
- `AuroraSecretArn` — Secrets Manager ARN for master creds
- `KnowledgeBaseId` — Bedrock KB id
- `KbDataSourceId` — KB data source id for S3 ingestion
- `FilingsDedupTable` — DynamoDB table name
- `S3RawBucket` / `S3ChunksBucket` / `S3DragDropBucket` — pipeline S3 bucket names
- `ResearchCdcQueueUrl` — SQS queue URL for SF -> Aurora CDC

Set these as Lambda environment variables on the MCP server Lambdas that need them, and in the skill layer where retriever is instantiated. The `seed-secrets.sh` helper reads the outputs and writes them to SSM under `/006-v3/infra/*`.

## What this stack is NOT

- **Not a prod stack.** Minimum viable infra to run the V3 demo reproducibly. Aurora serverless v2 min 0.5 ACU is appropriate for demo traffic; scale up for anything heavier.
- **Not multi-region.** `us-east-1` only. Cross-region replication is not wired.
- **Not Salesforce-aware.** The partner event source mapping for SF is referenced by arn; the SF side (CometD -> Partner Event) is configured in the SF org, not here.
- **Not the MCP Lambda stack.** MCP servers are provisioned by `aws/sam-template.yaml` (SAM, not CDK). They were kept in SAM because the MCP layer was already mature when CDK was added for the data layer.

## Idempotence

All stacks are safe to re-deploy. Aurora schema migration is wrapped in a CDK CustomResource that runs `001_init.sql` then `002_rls_policies.sql` — both use `IF NOT EXISTS` / `DROP POLICY IF EXISTS` guards.
