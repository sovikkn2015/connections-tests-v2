"""Salesforce Platform Event -> Aurora CDC handler.

Subscribes (via EventBridge fan-out from SF -> SQS) to two Platform Events:
  - Research_Memo_Change__e   - memo create / update / delete
  - Memo_Sharing_Change__e    - SF sharing rule change (principal_visibility)

For each event:
  1. Resolve memo fields from Salesforce REST (we need the body text, which
     the Platform Event does NOT carry — only the Id + change flag).
  2. If body changed: re-chunk + re-embed + replace chunks in Aurora.
  3. If sharing changed: upsert / delete principal_visibility rows.
  4. Hard MNPI fence: if contains_mnpi=TRUE, never send body text to any
     external index (we only store it in Aurora with RLS).

Environment:
  SF_INSTANCE_URL            https://<your-org>.my.salesforce.com
  SF_ACCESS_TOKEN_SECRET     Secrets Manager ARN -> JSON with access_token
  AURORA_SECRET_ARN          Aurora master creds (via RDS Data API would
                             be nicer; we use psycopg for pgvector support)
  AURORA_HOST / AURORA_DB    DB coordinates
  EMBED_MODEL_ID             amazon.titan-embed-text-v2:0

Zero credentials in env; all live in Secrets Manager.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import boto3
import psycopg
import requests

from .embedder import embed_batch
from .chunker import chunk_memo

logger = logging.getLogger()

_sm = boto3.client("secretsmanager")


def _secret_json(arn: str) -> dict:
    resp = _sm.get_secret_value(SecretId=arn)
    return json.loads(resp["SecretString"])


def _sf_access_token() -> str:
    arn = os.environ["SF_ACCESS_TOKEN_SECRET"]
    return _secret_json(arn)["access_token"]


def _fetch_memo(memo_id: str) -> dict:
    """Pull full memo record via SF REST."""
    url = f"{os.environ['SF_INSTANCE_URL']}/services/data/v60.0/sobjects/Research_Memo__c/{memo_id}"
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {_sf_access_token()}"},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def _aurora_conn():
    creds = _secret_json(os.environ["AURORA_SECRET_ARN"])
    return psycopg.connect(
        host=os.environ["AURORA_HOST"],
        dbname=os.environ["AURORA_DB"],
        user=creds["username"],
        password=creds["password"],
        autocommit=False,
    )


def _upsert_memo(cur: Any, memo: dict) -> None:
    cur.execute(
        "SELECT upsert_memo(%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (
            memo["Id"],
            memo.get("Title__c") or memo.get("Name") or "(untitled)",
            memo.get("OwnerId") or memo.get("CreatedById"),
            memo.get("Owner_Principal__c") or memo.get("CreatedById"),
            memo.get("Ticker__c"),
            memo.get("Sector__c"),
            memo.get("Classification__c") or "internal",
            bool(memo.get("Contains_MNPI__c")),
            memo.get("LastModifiedDate"),
        ),
    )


def _replace_chunks(cur: Any, memo: dict) -> int:
    body = memo.get("Body__c") or memo.get("Description__c") or ""
    if not body.strip():
        cur.execute("DELETE FROM research_chunk WHERE memo_id = %s", (memo["Id"],))
        return 0
    chunks = chunk_memo(body)
    embeddings = embed_batch([c for c in chunks])
    cur.execute("DELETE FROM research_chunk WHERE memo_id = %s", (memo["Id"],))
    for order, (text, vec) in enumerate(zip(chunks, embeddings, strict=False)):
        cur.execute(
            "INSERT INTO research_chunk (memo_id, chunk_order, text, embedding, token_count) "
            "VALUES (%s, %s, %s, %s, %s)",
            (memo["Id"], order, text, vec, len(text.split())),
        )
    return len(chunks)


def _apply_sharing(cur: Any, event: dict) -> None:
    """Apply a sharing-change event: add / remove principal_visibility rows."""
    memo_id = event.get("Memo_Id__c")
    principal = event.get("Principal_Id__c")
    action = (event.get("Action__c") or "add").lower()
    if not (memo_id and principal):
        return
    if action == "remove":
        cur.execute(
            "DELETE FROM principal_visibility WHERE memo_id = %s AND principal = %s",
            (memo_id, principal),
        )
    else:
        access = event.get("Access_Level__c") or "read"
        cur.execute(
            "INSERT INTO principal_visibility (memo_id, principal, access_level) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (principal, memo_id) DO UPDATE SET access_level = EXCLUDED.access_level",
            (memo_id, principal, access),
        )


def lambda_handler(event: dict, _context) -> dict:
    """SQS batch handler: process Platform Events one by one."""
    records = event.get("Records", [])
    processed = 0
    errors: list[dict] = []
    with _aurora_conn() as conn:
        with conn.cursor() as cur:
            for rec in records:
                try:
                    body = json.loads(rec["body"])
                    event_type = body.get("event_type", "")
                    if event_type == "Research_Memo_Change__e":
                        memo = _fetch_memo(body["memo_id"])
                        _upsert_memo(cur, memo)
                        n = _replace_chunks(cur, memo)
                        logger.info("memo %s re-indexed chunks=%d", memo["Id"], n)
                    elif event_type == "Memo_Sharing_Change__e":
                        _apply_sharing(cur, body)
                    else:
                        logger.warning("unknown event_type=%s", event_type)
                    processed += 1
                except Exception as exc:  # noqa: BLE001
                    logger.exception("cdc record failed")
                    errors.append({"id": rec.get("messageId"), "err": str(exc)[:200]})
        conn.commit()
    return {"processed": processed, "errors": errors}
