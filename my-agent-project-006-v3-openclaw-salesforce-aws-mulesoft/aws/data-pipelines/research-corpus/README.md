# Research Corpus Pipeline — Salesforce to Aurora pgvector

Salesforce Platform Event -> SQS -> Lambda -> Aurora PostgreSQL with pgvector + row-level security.

## Why Aurora + pgvector (and not Bedrock KB)

Internal research memos carry sharing rules. Salesforce's `Share__c` object and public-group hierarchy decide who sees what. **Bedrock KB metadata filters are a flat key-value dictionary, not a policy engine** — we cannot express "principal X can see memo Y if X is in public group G, and G is in the memo's sharing grant" via KB metadata alone.

Aurora + pgvector gets us:
- Native vector search with HNSW index
- Row-level security policies that mirror SF sharing rules exactly
- The same SQL engine the retriever already knows
- MNPI hard fence via `contains_mnpi` column + policy

EDGAR (public) goes in KB. Internal memos go here. The retriever fans out to both, merges with the reranker.

## Flow

```
Salesforce Research_Memo__c (insert/update/delete)
   |
   V  Platform Event Research_Memo_Change__e
   |
   V  EventBridge Partner Event Source (Salesforce)
   |
   V  SQS research-corpus-cdc-queue
   |
   V  cdc_handler.lambda_handler (batch size 10)
   |      fetch full memo via SF REST
   |      upsert research_memo
   |      chunk body (paragraph + sentence aware)
   |      embed chunks (Titan v2, 1024 dim, normalized)
   |      replace research_chunk rows (atomic tx)
   |
   V  Aurora PostgreSQL (pgvector HNSW + GIN full-text)

Sharing rule changes use the same path with Memo_Sharing_Change__e -> principal_visibility upserts.
```

## Schema

See `schema/001_init.sql` and `schema/002_rls_policies.sql`. Applied by CDK as a custom resource the first time the Aurora cluster comes up.

## Read-time principal filter

Every retrieval from the `openclaw/skills/rag/retriever.py` path:

1. opens a transaction
2. calls `set_principal_context(cursor, PrincipalContext(principal_id=..., role=...))`
3. runs the similarity query with the WHERE fragment from `principal_filter_sql(...)`
4. commits (or rolls back if anything fails)

RLS is the second fence: if the retriever forgets step 2, the database returns zero rows rather than leaking. Deliberate fail-closed.

## MNPI hard fence

`research_memo.contains_mnpi = TRUE` never propagates to:
- Bedrock KB (we never push MNPI to a public index)
- The LLM system prompt (chunks marked MNPI are filtered upstream of the model)
- The Langfuse trace body (scrubber runs before span emit)

The fence is enforced in three places — RLS policy, retriever read-time filter, and the Langfuse scrubber wrapper. Any one of them catches; all three must pass.

## Zero credentials

Everything — SF access token, Aurora master creds — lives in AWS Secrets Manager. The Lambda resolves them at invoke time via IAM role.
