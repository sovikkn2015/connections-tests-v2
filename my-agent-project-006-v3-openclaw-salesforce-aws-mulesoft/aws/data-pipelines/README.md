# V3 Data Pipelines

Two pipelines populate the two sides of the hybrid RAG:

| Pipeline | Source | Sink | Purpose |
|---|---|---|---|
| `filings-corpus/` | SEC EDGAR 10-K / 10-Q / 8-K | Bedrock Knowledge Base (S3 + OpenSearch Serverless) | Public filings, XBRL-parsed, section-aware chunked, Titan v2 embedded |
| `research-corpus/` | Salesforce `Research_Memo__c` + `IR_Position__c` via Platform Events | Aurora PostgreSQL + pgvector | Internal research memos with principal-scoped read-time filter that respects SF sharing rules |

Both feed the hybrid retriever in `openclaw/skills/rag/retriever.py`. The retriever fans out to both sinks in parallel, merges results with a reranker (`openclaw/skills/rag/reranker.py`), and returns citation-bound chunks.

## Why two sinks, not one

- **Bedrock KB** is purpose-built for Textract/PDF/XBRL ingestion and managed embeddings. We do not want to run that infrastructure ourselves.
- **Aurora + pgvector** gives us row-level security that mirrors Salesforce sharing rules. We cannot enforce SF sharing rules inside Bedrock KB metadata filters — KB metadata is a flat dictionary, not a policy engine. Aurora + RLS + a read-time principal filter is the right tool.

Splitting public (KB) from private (Aurora) keeps the MNPI fence clean: anything that might contain MNPI goes in Aurora with RLS; anything public (EDGAR) goes in KB without it.

## Layout

```
data-pipelines/
  filings-corpus/         EDGAR ingestion -> Bedrock KB
    lambdas/
      ingest_handler.py   EventBridge schedule -> /submissions index scan
      xbrl_parser.py      XBRL tag extraction (fin statement + risk factors)
      chunker.py          Section-aware chunker (10-K Items, 10-Q Parts)
      embedder.py         Titan v2 via Bedrock, batched
      kb_loader.py        POST to Bedrock KB sync api
      textract_handler.py S3-drop PDF -> Textract -> same pipeline
    requirements.txt
    README.md
  research-corpus/        Salesforce CDC -> Aurora pgvector
    lambdas/
      cdc_handler.py      Platform Event subscription -> upsert
      embedder.py         Titan v2 via Bedrock
      sharing_rules.py    Principal-scoped read-time filter
    schema/
      001_init.sql        Aurora schema: memos, embeddings, principals
      002_rls_policies.sql Row-level security policies
    requirements.txt
    README.md
```

## What the CDK stack provisions

`aws/cdk/` creates:

- Aurora PostgreSQL Serverless v2 cluster with pgvector extension
- Bedrock Knowledge Base with OpenSearch Serverless collection + S3 ingestion bucket
- EventBridge schedule (daily 04:00 ET) triggering `filings-corpus/ingest_handler`
- SQS + DLQ pair for Salesforce Platform Event ingestion (research-corpus)
- IAM roles with least-privilege access to Bedrock, S3, SSM
