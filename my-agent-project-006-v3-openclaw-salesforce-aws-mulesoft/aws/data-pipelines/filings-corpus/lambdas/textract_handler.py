"""S3 drag-drop PDF Textract handler.

When a user drops a PDF into `s3://${S3_DRAG_DROP_BUCKET}/drops/`, an S3
ObjectCreated event fires this Lambda. The Lambda:

  1. starts an async Textract job (`StartDocumentTextDetection`)
  2. once complete (via SNS or polling), pulls the text
  3. feeds text into chunker + embedder + kb_loader

This path exists so analysts can drop a research PDF (investor deck,
broker note) directly into KB without waiting on EDGAR's next scan.

Two-shot design: this module handles step 1 (start job) and step 2 (on
the SNS completion callback). Splitting keeps the Lambda timeout low.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from typing import Any

import boto3

from .chunker import chunk_filing
from .kb_loader import stage_chunks, start_ingestion

logger = logging.getLogger()

_textract = boto3.client("textract")
_s3 = boto3.client("s3")


def _start_text_detection(bucket: str, key: str) -> str:
    resp = _textract.start_document_text_detection(
        DocumentLocation={"S3Object": {"Bucket": bucket, "Name": key}},
        NotificationChannel=(
            {
                "SNSTopicArn": os.environ["TEXTRACT_SNS_TOPIC_ARN"],
                "RoleArn": os.environ["TEXTRACT_ROLE_ARN"],
            }
            if "TEXTRACT_SNS_TOPIC_ARN" in os.environ
            else None
        ),
        JobTag=key[:64],
    )
    return resp["JobId"]


def _collect_text(job_id: str) -> str:
    """Pull all text pages from a completed Textract job."""
    parts: list[str] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"JobId": job_id, "MaxResults": 1000}
        if token:
            kwargs["NextToken"] = token
        resp = _textract.get_document_text_detection(**kwargs)
        for block in resp.get("Blocks", []):
            if block.get("BlockType") == "LINE":
                parts.append(block.get("Text", ""))
        token = resp.get("NextToken")
        if not token:
            break
    return "\n".join(parts)


def on_s3_create(event: dict, _context) -> dict:
    """Entry for the S3 ObjectCreated -> start Textract path."""
    rec = event["Records"][0]["s3"]
    bucket = rec["bucket"]["name"]
    key = urllib.parse.unquote_plus(rec["object"]["key"])
    if not key.lower().endswith(".pdf"):
        return {"skipped": True, "reason": "not_pdf", "key": key}
    job_id = _start_text_detection(bucket, key)
    logger.info("started textract job=%s bucket=%s key=%s", job_id, bucket, key)
    return {"job_id": job_id, "bucket": bucket, "key": key}


def on_textract_complete(event: dict, _context) -> dict:
    """Entry for the Textract SNS 'succeeded' callback -> chunk + embed + KB-load."""
    msg = json.loads(event["Records"][0]["Sns"]["Message"])
    job_id = msg["JobId"]
    status = msg["Status"]
    if status != "SUCCEEDED":
        logger.warning("textract job %s status=%s; skipping", job_id, status)
        return {"skipped": True, "reason": status, "job_id": job_id}
    tag = msg.get("JobTag", "unknown")
    text = _collect_text(job_id)
    chunks = chunk_filing(text, form="PDF", cik="pdf-drop", accession=tag)
    staged = stage_chunks(chunks, cik="pdf-drop", accession=tag)
    ingestion_id = start_ingestion()
    return {
        "job_id": job_id,
        "tag": tag,
        "chunks": len(chunks),
        "staged": staged,
        "ingestion_id": ingestion_id,
    }
