"""EDGAR ingestion handler - daily scheduled Lambda.

Scans SEC EDGAR /submissions for recent 10-K / 10-Q / 8-K filings on the
watchlist universe (tracked tickers stored in SSM), downloads the primary
document (HTML or XBRL), and pushes it through the pipeline:

    EDGAR -> xbrl_parser -> chunker -> embedder -> kb_loader -> Bedrock KB

Triggered by EventBridge at 04:00 America/New_York daily. Also idempotent
on reinvocation — dedup is keyed on (cik, accession_number).

Environment:
    WATCHLIST_SSM_PARAM      /006-v3/watchlist/tickers (comma-separated)
    KB_ID                    Bedrock Knowledge Base id (from CDK output)
    KB_DATA_SOURCE_ID        KB data source id to start sync on
    S3_RAW_BUCKET            S3 bucket where raw filings land
    S3_CHUNKS_BUCKET         S3 bucket where chunked docs land
    DEDUP_TABLE              DynamoDB table for cik#accession dedup
    USER_AGENT               Required by SEC EDGAR. Set to a real contact.

No credentials in this module. boto3 resolves IAM from the execution role.
SEC EDGAR requires a descriptive User-Agent; if missing we fail closed
with a clear error instead of hammering the feed anonymously.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any
from urllib.parse import quote

import boto3
import requests

logger = logging.getLogger()
logger.setLevel(logging.INFO)

EDGAR_BASE = "https://data.sec.gov"
EDGAR_ARCHIVES = "https://www.sec.gov/Archives"
FILING_TYPES = {"10-K", "10-Q", "8-K"}

_ssm = boto3.client("ssm")
_s3 = boto3.client("s3")
_ddb = boto3.resource("dynamodb")
_bedrock_agent = boto3.client("bedrock-agent")


def _user_agent() -> str:
    ua = os.environ.get("USER_AGENT", "").strip()
    if not ua or "@" not in ua:
        raise RuntimeError(
            "USER_AGENT env var required by SEC EDGAR (format: 'Contact Name contact@example.com')"
        )
    return ua


def _get_watchlist() -> list[str]:
    param = os.environ.get("WATCHLIST_SSM_PARAM", "/006-v3/watchlist/tickers")
    resp = _ssm.get_parameter(Name=param)
    raw = (resp.get("Parameter") or {}).get("Value", "")
    return [t.strip().upper() for t in raw.split(",") if t.strip()]


def _ticker_to_cik(ticker: str) -> str | None:
    """Resolve ticker -> 10-digit zero-padded CIK via EDGAR's company_tickers.json."""
    url = f"{EDGAR_BASE}/files/company_tickers.json"
    r = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
    r.raise_for_status()
    for _k, v in r.json().items():
        if v.get("ticker", "").upper() == ticker:
            return str(v["cik_str"]).zfill(10)
    return None


def _recent_filings(cik: str) -> list[dict[str, Any]]:
    """List the most recent filings for a CIK."""
    url = f"{EDGAR_BASE}/submissions/CIK{cik}.json"
    r = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=30)
    r.raise_for_status()
    data = r.json()
    recent = (data.get("filings") or {}).get("recent") or {}
    out = []
    forms = recent.get("form", [])
    accs = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    primary = recent.get("primaryDocument", [])
    for i, form in enumerate(forms):
        if form not in FILING_TYPES:
            continue
        out.append(
            {
                "form": form,
                "accession_number": accs[i],
                "filing_date": dates[i],
                "primary_document": primary[i] if i < len(primary) else "",
                "cik": cik,
            }
        )
    return out[:50]


def _already_ingested(cik: str, accession: str) -> bool:
    tbl_name = os.environ.get("DEDUP_TABLE")
    if not tbl_name:
        return False
    tbl = _ddb.Table(tbl_name)
    resp = tbl.get_item(Key={"cik_accession": f"{cik}#{accession}"})
    return "Item" in resp


def _mark_ingested(cik: str, accession: str, form: str) -> None:
    tbl_name = os.environ.get("DEDUP_TABLE")
    if not tbl_name:
        return
    tbl = _ddb.Table(tbl_name)
    tbl.put_item(
        Item={
            "cik_accession": f"{cik}#{accession}",
            "cik": cik,
            "accession": accession,
            "form": form,
            "ingested_at": int(time.time()),
        }
    )


def _download_primary(cik: str, accession: str, doc: str) -> bytes:
    """Download the primary filing document from EDGAR Archives."""
    acc_nodash = accession.replace("-", "")
    url = f"{EDGAR_ARCHIVES}/edgar/data/{int(cik)}/{acc_nodash}/{quote(doc)}"
    r = requests.get(url, headers={"User-Agent": _user_agent()}, timeout=60)
    r.raise_for_status()
    return r.content


def _put_raw(cik: str, accession: str, body: bytes, content_type: str) -> str:
    bucket = os.environ["S3_RAW_BUCKET"]
    key = f"edgar/{cik}/{accession}/primary.html"
    _s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    return f"s3://{bucket}/{key}"


def _trigger_kb_sync() -> None:
    kb_id = os.environ.get("KB_ID")
    ds_id = os.environ.get("KB_DATA_SOURCE_ID")
    if not (kb_id and ds_id):
        logger.warning("KB_ID / KB_DATA_SOURCE_ID not set; skipping KB sync")
        return
    _bedrock_agent.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)


def lambda_handler(event: dict, _context) -> dict:
    """Entry point. Returns a summary of what was ingested."""
    logger.info("EDGAR ingest start")
    tickers = _get_watchlist()
    ingested: list[dict] = []
    skipped: list[dict] = []
    failed: list[dict] = []

    for ticker in tickers:
        try:
            cik = _ticker_to_cik(ticker)
            if not cik:
                failed.append({"ticker": ticker, "reason": "cik_not_found"})
                continue
            for filing in _recent_filings(cik):
                acc = filing["accession_number"]
                if _already_ingested(cik, acc):
                    skipped.append({"ticker": ticker, "accession": acc})
                    continue
                body = _download_primary(cik, acc, filing["primary_document"])
                ct = "text/html" if filing["primary_document"].endswith(".htm") else "application/xml"
                s3_uri = _put_raw(cik, acc, body, ct)
                _mark_ingested(cik, acc, filing["form"])
                ingested.append(
                    {
                        "ticker": ticker,
                        "cik": cik,
                        "accession": acc,
                        "form": filing["form"],
                        "s3_uri": s3_uri,
                    }
                )
                # SEC rate limit: 10 requests / sec. We do ~3 per filing.
                time.sleep(0.35)
        except Exception as exc:  # noqa: BLE001
            logger.exception("ingest failed ticker=%s", ticker)
            failed.append({"ticker": ticker, "reason": str(exc)[:200]})

    if ingested:
        _trigger_kb_sync()

    summary = {
        "ingested_count": len(ingested),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "ingested": ingested[:10],
        "failed": failed[:10],
    }
    logger.info("EDGAR ingest done %s", json.dumps(summary))
    return summary
