# Filings Corpus Pipeline — EDGAR to Bedrock KB

Daily scheduled ingestion of SEC 10-K / 10-Q / 8-K filings for the tracked universe.

## Flow

```
EventBridge (04:00 ET daily)
  -> ingest_handler.lambda_handler
       -> read watchlist from SSM /006-v3/watchlist/tickers
       -> for each ticker:
            resolve ticker -> CIK
            list recent filings
            skip already-ingested (DynamoDB dedup)
            download primary document
            put to s3://${S3_RAW_BUCKET}/edgar/{cik}/{accession}/primary.html
            mark ingested
       -> start Bedrock KB ingestion job

S3 drop path (ad-hoc):
  s3://${S3_DRAG_DROP_BUCKET}/drops/{some.pdf}
  -> on_s3_create (Textract start)
  -> SNS "SUCCEEDED" -> on_textract_complete
       -> chunk_filing -> stage_chunks -> start_ingestion
```

## Modules

| File | Role |
|---|---|
| `ingest_handler.py` | Main scheduled handler. Resolves tickers -> CIKs, scans /submissions, dedups via DynamoDB, downloads filings to S3, triggers KB sync. |
| `xbrl_parser.py` | Inline-XBRL + classic XBRL fact extractor. Pulls 8 canonical concepts (revenue, net_income, assets, liabilities, equity, OCF, LTD, STD). |
| `chunker.py` | Section-aware splitter honoring 10-K Item / 10-Q Part boundaries. Never splits a sentence. |
| `embedder.py` | Titan v2 batched embedder (1024 dim, normalized). Used by both pipelines. |
| `kb_loader.py` | Renders chunks to Bedrock KB custom-chunking JSONL, stages to S3, triggers ingestion. |
| `textract_handler.py` | Ad-hoc PDF drag-drop path. Two-shot (S3 event starts job, SNS callback finishes). |

## Environment variables

| Var | Purpose | Default |
|---|---|---|
| `USER_AGENT` | Required by SEC EDGAR | (none — fails closed) |
| `WATCHLIST_SSM_PARAM` | SSM parameter name (comma-separated tickers) | `/006-v3/watchlist/tickers` |
| `DEDUP_TABLE` | DynamoDB table name | (set by CDK) |
| `S3_RAW_BUCKET` | Raw filings S3 bucket | (set by CDK) |
| `S3_CHUNKS_BUCKET` | KB-watched chunks bucket | (set by CDK) |
| `KB_ID` | Bedrock Knowledge Base id | (set by CDK output) |
| `KB_DATA_SOURCE_ID` | KB data source id | (set by CDK output) |
| `EMBED_MODEL_ID` | Titan embed model id | `amazon.titan-embed-text-v2:0` |
| `TEXTRACT_SNS_TOPIC_ARN` | SNS for Textract completion | (optional) |
| `TEXTRACT_ROLE_ARN` | IAM role Textract assumes for SNS publish | (optional) |

## What's intentionally not done

- **Amendment tracking.** 10-K/A filings are ingested as standalone documents; we don't mark the original as superseded. The retriever always prefers the most recent (period_end) for financial facts, so this is fine for research queries but wrong for compliance-grade auditing.
- **Index file parsing.** We pull the `primary_document` from `submissions.json`, not the filing index. Some filings have multiple exhibit-level XBRL instances; we ingest only the primary.
- **Full XBRL taxonomy.** Eight concepts, listed in `xbrl_parser.CONCEPT_MAP`. Everything else is dropped. This is deliberate — full taxonomy coverage is not a demo requirement.

## Tests

Unit tests for parser + chunker live in `tests/data-pipelines/filings-corpus/`. The ingest_handler itself is integration-tested against moto (mocked AWS) in the same suite.

## Zero credentials in git

Watchlist is SSM; AWS creds are IAM roles; EDGAR needs only a User-Agent contact string (set via env var at deploy, not hardcoded).
