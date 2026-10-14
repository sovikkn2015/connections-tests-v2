"""V3 sec-edgar MCP server.

Tools:
- get_latest_filing(symbol, type)          - latest 10-K / 10-Q / 8-K metadata
- get_filing_sections(accession_num)       - Item 1A + Item 7 extracted
- get_financial_statements(symbol, period) - Income/Balance/Cash Flow

Backend: SEC EDGAR public API (no key). Rate-limited to 10 req/sec per
SEC fair-use. User-Agent required and set from SEC_EDGAR_UA env var.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _base import McpServer, McpUpstreamError, McpValidationError, ToolSpec  # noqa: E402
from _fixtures import (  # noqa: E402
    MOCK_SOURCE_CHUNKS,
    MOCK_SOURCE_TABLES,
    empty_source_chunk,
    empty_source_table,
)
from _parser import extract_item, parse_latest_filing_meta  # noqa: E402

EDGAR_BASE = "https://www.sec.gov"
EDGAR_DATA = "https://data.sec.gov"
UA = os.environ.get("SEC_EDGAR_UA", "006-v3 research-agent platform-ops@example.com")
MOCK_MODE = os.environ.get("SEC_EDGAR_MODE", "live").lower() == "mock"

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_CIK_CACHE: dict[str, str] = {}
_CIK_LOCK = Lock()

_MIN_INTERVAL = 0.10
_LAST_CALL = [0.0]
_RATE_LOCK = Lock()


def _ratelimit() -> None:
    with _RATE_LOCK:
        now = time.time()
        delta = now - _LAST_CALL[0]
        if delta < _MIN_INTERVAL:
            time.sleep(_MIN_INTERVAL - delta)
        _LAST_CALL[0] = time.time()


def _edgar_get(url: str) -> httpx.Response:
    _ratelimit()
    headers = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}
    try:
        with httpx.Client(timeout=20.0, follow_redirects=True) as client:
            return client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise McpUpstreamError(f"EDGAR network error: {exc}") from exc


def _load_cik_map() -> dict[str, str]:
    with _CIK_LOCK:
        if _CIK_CACHE:
            return _CIK_CACHE
        if MOCK_MODE:
            _CIK_CACHE.update({"NVDA": "0001045810", "AAPL": "0000320193", "MSFT": "0000789019"})
            return _CIK_CACHE
        resp = _edgar_get(f"{EDGAR_BASE}/files/company_tickers.json")
        if not resp.is_success:
            raise McpUpstreamError(f"EDGAR tickers fetch {resp.status_code}")
        data = resp.json()
        for _, row in data.items():
            ticker = str(row.get("ticker", "")).upper()
            cik = str(row.get("cik_str", "")).zfill(10)
            if ticker and cik:
                _CIK_CACHE[ticker] = cik
        return _CIK_CACHE


def _cik_for(symbol: str) -> str:
    sym = symbol.strip().upper()
    cik_map = _load_cik_map()
    if sym not in cik_map:
        raise McpValidationError(f"Unknown ticker: {sym}")
    return cik_map[sym]


def _validate_symbol(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise McpValidationError("'symbol' must be a non-empty string")
    return raw.strip().upper()


def _validate_filing_type(raw: Any) -> str:
    if not isinstance(raw, str):
        raise McpValidationError("'type' must be a string")
    t = raw.strip().upper()
    if t not in {"10-K", "10-Q", "8-K", "DEF 14A", "20-F"}:
        raise McpValidationError("'type' must be one of 10-K, 10-Q, 8-K, DEF 14A, 20-F")
    return t


def _mock_filing(symbol: str, filing_type: str) -> dict:
    return {
        "symbol": symbol,
        "filing_type": filing_type,
        "accessionNumber": "0001045810-26-000042",
        "filingDate": "2026-02-25",
        "primaryDocument": f"{symbol.lower()}-10q.htm",
        "url": f"https://www.sec.gov/Archives/edgar/data/1045810/000104581026000042/{symbol.lower()}-10q.htm",
        "dataSource": "mock",
    }


def _mock_sections() -> dict:
    return {
        "sections": [
            {
                "item": "1A",
                "title": "Item 1A. Risk Factors",
                "text": (
                    "Supply chain concentration in Asia-Pacific subjects us to geopolitical risk. "
                    "Export control regulations targeting advanced semiconductors have impacted "
                    "revenue in China. Cyclical demand for AI accelerators introduces volatility."
                ),
            },
            {
                "item": "7",
                "title": "Item 7. Management's Discussion and Analysis",
                "text": (
                    "Data center revenue grew year-over-year driven by continued adoption of "
                    "generative AI workloads. Gross margin expanded due to favorable product mix. "
                    "Operating expenses rose as we invested in R&D for next-generation architectures."
                ),
            },
        ],
        "dataSource": "mock",
    }


def _mock_financials(symbol: str, period: str) -> dict:
    base = 1_000_000_000 + (sum(ord(c) for c in symbol) * 10_000_000)
    return {
        "symbol": symbol,
        "period": period,
        "filing_type": "10-Q",
        "income_statement": {
            "period": period,
            "revenue": {"label": "Revenue", "value": base * 22, "unit": "USD"},
            "gross_profit": {"label": "Gross profit", "value": base * 16, "unit": "USD"},
            "operating_income": {"label": "Operating income", "value": base * 11, "unit": "USD"},
            "net_income": {"label": "Net income", "value": base * 9, "unit": "USD"},
        },
        "balance_sheet": {
            "period": period,
            "total_assets": {"label": "Total assets", "value": base * 65, "unit": "USD"},
            "total_liabilities": {"label": "Total liabilities", "value": base * 25, "unit": "USD"},
            "total_equity": {"label": "Total equity", "value": base * 40, "unit": "USD"},
        },
        "cash_flow": {
            "period": period,
            "operating_cash_flow": {"label": "Operating cash flow", "value": base * 12, "unit": "USD"},
        },
        "dataSource": "mock",
    }


def handle_get_latest_filing(args: dict, ctx: dict) -> dict:
    symbol = _validate_symbol(args.get("symbol"))
    filing_type = _validate_filing_type(args.get("type", "10-K"))

    if MOCK_MODE:
        return _mock_filing(symbol, filing_type)

    cik = _cik_for(symbol)
    resp = _edgar_get(f"{EDGAR_DATA}/submissions/CIK{cik}.json")
    if not resp.is_success:
        raise McpUpstreamError(f"EDGAR submissions {resp.status_code}")

    payload = resp.json()
    meta = parse_latest_filing_meta(payload, filing_type)
    if not meta:
        raise McpUpstreamError(f"No {filing_type} filing found for {symbol}")

    accession = (meta["accessionNumber"] or "").replace("-", "")
    primary = meta["primaryDocument"] or ""
    url = f"{EDGAR_BASE}/Archives/edgar/data/{int(cik)}/{accession}/{primary}" if primary else ""

    return {
        "symbol": symbol,
        "filing_type": meta["form"],
        "accessionNumber": meta["accessionNumber"],
        "filingDate": meta["filingDate"],
        "primaryDocument": primary,
        "url": url,
        "dataSource": "sec-edgar",
    }


def handle_get_filing_sections(args: dict, ctx: dict) -> dict:
    accession = args.get("accession_num")
    if not isinstance(accession, str) or not accession:
        raise McpValidationError("'accession_num' required")
    cik_arg = args.get("cik")
    url_override = args.get("url")

    if MOCK_MODE:
        return _mock_sections()

    if url_override:
        resp = _edgar_get(url_override)
    else:
        if not cik_arg:
            raise McpValidationError("'cik' or 'url' required alongside accession_num")
        idx_url = f"{EDGAR_BASE}/cgi-bin/browse-edgar?action=getcompany&CIK={cik_arg}&type=10-K&dateb=&owner=include&count=40"
        resp = _edgar_get(idx_url)

    if not resp.is_success:
        raise McpUpstreamError(f"EDGAR filing fetch {resp.status_code}")

    html = resp.text
    sections = []
    for item_id in ("1A", "7"):
        sec = extract_item(html, item_id)
        if sec:
            sections.append(sec.model_dump())

    if not sections:
        return {
            "sections": [],
            "note": "Could not extract Item 1A / Item 7 from this filing; may be an image-based PDF or unusual layout.",
            "dataSource": "sec-edgar",
        }

    return {"sections": sections, "dataSource": "sec-edgar"}


def handle_get_financial_statements(args: dict, ctx: dict) -> dict:
    symbol = _validate_symbol(args.get("symbol"))
    period = args.get("period")
    if not isinstance(period, str) or not period.strip():
        period = datetime.now(tz=timezone.utc).strftime("%Y-%m")

    if MOCK_MODE:
        return _mock_financials(symbol, period)

    cik = _cik_for(symbol)
    resp = _edgar_get(f"{EDGAR_DATA}/api/xbrl/companyfacts/CIK{cik}.json")
    if not resp.is_success:
        raise McpUpstreamError(f"EDGAR companyfacts {resp.status_code}")

    facts = resp.json().get("facts", {}).get("us-gaap", {})

    def _latest(tag: str, label: str, unit: str = "USD") -> dict | None:
        node = facts.get(tag)
        if not node:
            return None
        units = node.get("units") or {}
        vals = units.get(unit) or units.get("USD/shares") or []
        if not vals:
            return None
        pick = max(vals, key=lambda v: v.get("end", ""))
        return {"label": label, "value": pick.get("val"), "unit": unit}

    return {
        "symbol": symbol,
        "period": period,
        "filing_type": "10-Q/10-K (companyfacts)",
        "income_statement": {
            "period": period,
            "revenue": _latest("Revenues", "Revenue") or _latest("SalesRevenueNet", "Revenue"),
            "gross_profit": _latest("GrossProfit", "Gross profit"),
            "operating_income": _latest("OperatingIncomeLoss", "Operating income"),
            "net_income": _latest("NetIncomeLoss", "Net income"),
        },
        "balance_sheet": {
            "period": period,
            "total_assets": _latest("Assets", "Total assets"),
            "total_liabilities": _latest("Liabilities", "Total liabilities"),
            "total_equity": _latest("StockholdersEquity", "Total equity"),
        },
        "cash_flow": {
            "period": period,
            "operating_cash_flow": _latest("NetCashProvidedByUsedInOperatingActivities", "Operating cash flow"),
        },
        "dataSource": "sec-edgar",
    }


def _validate_source_id(raw: Any) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise McpValidationError("'source_id' must be a non-empty string")
    sid = raw.strip()
    # source_id character set: alphanumerics, dash, underscore. Minted by the
    # filings-corpus chunker — anything outside this charset is a client bug.
    for ch in sid:
        if not (ch.isalnum() or ch in "-_"):
            raise McpValidationError(
                "'source_id' must match ^[A-Za-z0-9_-]+$"
            )
    return sid


def handle_get_source_table(args: dict, ctx: dict) -> dict:
    """Look up a pre-indexed table by source_id.

    source_id follows the pattern ``<cik>-<accession>-tab-<n>`` (minted by
    the filings-corpus chunker). In mock mode we return a fixture table
    for a handful of well-known ids; in live mode we query the chunks
    bucket. The filings-corpus catalog build is not in V3, so tables
    are not yet produced in live — return an empty stub.
    """
    source_id = _validate_source_id(args.get("source_id"))

    if MOCK_MODE:
        return MOCK_SOURCE_TABLES.get(source_id) or empty_source_table(source_id)

    # Live mode placeholder — filings-corpus table extraction not yet
    # deployed. Chart rendering gracefully shows "source not available".
    logger.warning(
        "sec-edgar get_source_table: live table extraction not implemented; source_id=%s",
        source_id,
    )
    return empty_source_table(source_id)


def _s3_get_chunk(source_id: str) -> dict | None:
    """Fetch chunk JSON from the KB chunks bucket by source_chunk_id."""
    bucket = os.environ.get("KB_CHUNKS_BUCKET", "")
    if not bucket:
        return None
    try:
        import boto3  # noqa: PLC0415
    except ImportError:
        return None
    key_prefix = os.environ.get("KB_CHUNKS_PREFIX", "kb-chunks/")
    key = f"{key_prefix}{source_id}.json"
    try:
        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        obj = s3.get_object(Bucket=bucket, Key=key)
        import json as _json  # noqa: PLC0415
        body = _json.loads(obj["Body"].read().decode("utf-8"))
        return body
    except Exception as exc:  # noqa: BLE001
        logger.warning("s3 chunk lookup failed for %s: %s", source_id, exc)
        return None


def handle_get_source_chunk(args: dict, ctx: dict) -> dict:
    """Look up a pre-indexed text chunk by source_id.

    Live mode: read the chunk JSON directly from the KB ChunksBucket
    (s3://<bucket>/<prefix>/<source_chunk_id>.json). These are the
    same chunks the KB ingestion job indexed, so the source_chunk_id
    returned by ``kb_retrieve`` always drills down to a real excerpt.
    """
    source_id = _validate_source_id(args.get("source_id"))

    if MOCK_MODE:
        return MOCK_SOURCE_CHUNKS.get(source_id) or empty_source_chunk(source_id)

    body = _s3_get_chunk(source_id)
    if not body:
        return empty_source_chunk(source_id)

    md = body.get("metadata", {})
    return {
        "source_id": source_id,
        "label": md.get("ticker", "") + " " + md.get("form", ""),
        "text": body.get("text", ""),
        "source_url": md.get("source_url", ""),
        "filing_date": md.get("filing_date", ""),
        "accession": md.get("accession", ""),
        "ticker": md.get("ticker", ""),
        "form": md.get("form", ""),
        "dataSource": "bedrock-kb-chunks",
    }


def handle_kb_retrieve(args: dict, ctx: dict) -> dict:
    """Semantic retrieval from the Bedrock Knowledge Base.

    Uses bedrock-agent-runtime Retrieve against the knowledge_base_id
    configured via env (BEDROCK_KB_ID). Returns the top-N chunks with
    source_chunk_id, text excerpt, and similarity score. The calling
    agent is expected to pass these into the synthesis prompt as context
    and emit [src:<source_chunk_id>] citations that the UI chips resolve
    via ``get_source_chunk``.
    """
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise McpValidationError("'query' must be a non-empty string")
    top_k = args.get("top_k", 6)
    if not isinstance(top_k, int) or top_k < 1 or top_k > 20:
        raise McpValidationError("'top_k' must be an integer in [1, 20]")

    kb_id = os.environ.get("BEDROCK_KB_ID", "")
    if MOCK_MODE or not kb_id:
        # Deterministic mock payload keyed off query — no silent success.
        if not kb_id and not MOCK_MODE:
            raise McpUpstreamError("BEDROCK_KB_ID not configured; live KB retrieval unavailable")
        return {
            "query": query,
            "results": [
                {
                    "source_chunk_id": "MOCK-chunk-001",
                    "text": f"(mock) excerpt relevant to: {query[:80]}",
                    "score": 0.85,
                    "ticker": "MOCK",
                    "form": "10-Q",
                }
            ],
            "dataSource": "mock",
        }

    try:
        import boto3  # noqa: PLC0415
    except ImportError as exc:
        raise McpUpstreamError(f"boto3 not available: {exc}")

    region = os.environ.get("AWS_REGION_BEDROCK", os.environ.get("AWS_REGION", "us-east-1"))
    try:
        bar = boto3.client("bedrock-agent-runtime", region_name=region)
        resp = bar.retrieve(
            knowledgeBaseId=kb_id,
            retrievalQuery={"text": query[:1000]},
            retrievalConfiguration={
                "vectorSearchConfiguration": {"numberOfResults": top_k},
            },
        )
    except Exception as exc:  # noqa: BLE001
        raise McpUpstreamError(f"Bedrock KB retrieve failed: {exc}") from exc

    results = []
    for r in resp.get("retrievalResults", []):
        text_content = r.get("content", {}).get("text", "")
        score = float(r.get("score", 0.0))
        # The KB content is a JSON-serialized chunk (see seed-kb-chunks.py),
        # so parse out the nested text + metadata if possible.
        chunk_text = text_content
        metadata = {}
        try:
            import json as _json  # noqa: PLC0415
            parsed = _json.loads(text_content)
            if isinstance(parsed, dict):
                chunk_text = parsed.get("text", text_content)
                metadata = parsed.get("metadata", {})
        except (ValueError, TypeError):
            pass
        source_chunk_id = metadata.get("source_chunk_id", "")
        if not source_chunk_id:
            # Fall back to deriving from S3 URI
            s3_uri = r.get("location", {}).get("s3Location", {}).get("uri", "")
            if s3_uri.endswith(".json"):
                source_chunk_id = s3_uri.rsplit("/", 1)[-1][:-5]
        results.append(
            {
                "source_chunk_id": source_chunk_id,
                "text": chunk_text[:1200],
                "score": round(score, 4),
                "ticker": metadata.get("ticker", ""),
                "form": metadata.get("form", ""),
                "filing_date": metadata.get("filing_date", ""),
                "accession": metadata.get("accession", ""),
                "source_url": metadata.get("source_url", ""),
            }
        )

    return {
        "query": query,
        "results": results,
        "dataSource": "bedrock-kb",
        "knowledgeBaseId": kb_id,
    }


server = McpServer(
    name="sec-edgar",
    version="3.0.0",
    description="SEC EDGAR filings — metadata, Item 1A/Item 7 extraction, financial statements (XBRL).",
)

server.register(
    ToolSpec(
        name="get_latest_filing",
        description="Return metadata for the most recent filing of the given type for a ticker.",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "type": {"type": "string", "enum": ["10-K", "10-Q", "8-K", "DEF 14A", "20-F"]},
            },
            "required": ["symbol", "type"],
        },
    ),
    handle_get_latest_filing,
)
server.register(
    ToolSpec(
        name="get_filing_sections",
        description="Extract Item 1A (Risk Factors) and Item 7 (MD&A) as structured sections.",
        input_schema={
            "type": "object",
            "properties": {
                "accession_num": {"type": "string"},
                "cik": {"type": "string"},
                "url": {"type": "string", "description": "Direct URL to the filing HTML — skips lookup."},
            },
            "required": ["accession_num"],
        },
    ),
    handle_get_filing_sections,
)
server.register(
    ToolSpec(
        name="get_financial_statements",
        description="Income Statement, Balance Sheet, Cash Flow extracted from XBRL companyfacts.",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "period": {"type": "string", "description": "Period label like '2026-Q1'"},
            },
            "required": ["symbol"],
        },
    ),
    handle_get_financial_statements,
)
server.register(
    ToolSpec(
        name="get_source_table",
        description="Fetch a pre-indexed financial table by source_id for chart rendering.",
        input_schema={
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$"},
            },
            "required": ["source_id"],
        },
    ),
    handle_get_source_table,
)
server.register(
    ToolSpec(
        name="get_source_chunk",
        description="Fetch a pre-indexed text chunk by source_id for citation drill-down.",
        input_schema={
            "type": "object",
            "properties": {
                "source_id": {"type": "string", "pattern": "^[A-Za-z0-9_-]+$"},
            },
            "required": ["source_id"],
        },
    ),
    handle_get_source_chunk,
)
server.register(
    ToolSpec(
        name="kb_retrieve",
        description="Semantic retrieval from the Bedrock Knowledge Base of SEC filings. Returns top-N chunks with source_chunk_id for citation.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Natural-language retrieval query", "minLength": 1},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 6},
            },
            "required": ["query"],
        },
    ),
    handle_kb_retrieve,
)


def lambda_handler(event, context):
    return server.handle(event, context)
