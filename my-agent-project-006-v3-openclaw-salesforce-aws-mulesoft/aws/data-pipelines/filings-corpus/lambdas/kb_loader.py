"""Bedrock Knowledge Base chunk loader.

The EDGAR pipeline stages chunks (with section metadata) as individual S3
objects under `s3://${S3_CHUNKS_BUCKET}/kb-chunks/...`. Bedrock KB watches
that prefix via its configured data source. This module:

  1. converts our internal Chunk objects into KB-expected JSONL records
  2. writes them to S3 under the KB's watched prefix
  3. optionally starts an ingestion job to force resync

KB metadata schema used here (KB filter-able):
  cik, accession, form, section, order, period_end

KB ingestion runs asynchronously; we do NOT wait for completion in the
Lambda — that's a separate status-polling job. The ingest_handler kicks a
sync and returns.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Iterable

import boto3

from .chunker import Chunk

logger = logging.getLogger()

_s3 = boto3.client("s3")
_bedrock_agent = boto3.client("bedrock-agent")


def _to_kb_record(c: Chunk) -> dict:
    """Render a chunk as the Bedrock KB custom-chunking JSONL record."""
    return {
        "content": {"type": "TEXT", "text": c.text},
        "metadata": {
            "cik": c.cik,
            "accession": c.accession,
            "form": c.form,
            "section": c.section,
            "order": c.order,
        },
    }


def stage_chunks(chunks: Iterable[Chunk], *, cik: str, accession: str) -> str:
    """Write all chunks for one filing to one JSONL file in the KB-watched prefix."""
    bucket = os.environ["S3_CHUNKS_BUCKET"]
    key = f"kb-chunks/{cik}/{accession}.jsonl"
    body = "\n".join(json.dumps(_to_kb_record(c)) for c in chunks)
    _s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=body.encode("utf-8"),
        ContentType="application/x-ndjson",
    )
    return f"s3://{bucket}/{key}"


def start_ingestion() -> str | None:
    """Kick a KB ingestion job. Returns the job id."""
    kb_id = os.environ.get("KB_ID")
    ds_id = os.environ.get("KB_DATA_SOURCE_ID")
    if not (kb_id and ds_id):
        logger.warning("KB_ID / KB_DATA_SOURCE_ID missing; skip ingestion")
        return None
    resp = _bedrock_agent.start_ingestion_job(
        knowledgeBaseId=kb_id, dataSourceId=ds_id
    )
    return (resp.get("ingestionJob") or {}).get("ingestionJobId")
