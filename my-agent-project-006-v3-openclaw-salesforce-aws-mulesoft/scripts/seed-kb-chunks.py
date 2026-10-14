#!/usr/bin/env python3
"""Chunk the downloaded SEC filings and upload as KB-compatible JSON.

The Bedrock KB data source is configured to scan `s3://chunks-bucket/kb-chunks/*.json`.
Each JSON is one chunk with fields { text, metadata }. KB's Titan embedder + FAISS
vector index does the rest; no external embedding pipeline needed because KB embeds
at ingestion time.

Real text, real chunks. No mock data.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from bs4 import BeautifulSoup  # type: ignore[import-untyped]

REGION = "us-east-1"
DEFAULT_CHUNK_SIZE = 1500
DEFAULT_OVERLAP = 200


def html_to_text(html: bytes) -> str:
    """Strip HTML/XBRL to clean text. EDGAR filings are DFIN-formatted XBRL-in-HTML."""
    soup = BeautifulSoup(html, "html.parser")
    # Remove hidden XBRL tags and script/style
    for tag in soup(["script", "style", "ix:references", "ix:resources", "ix:hidden"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[str]:
    """Simple character-window chunker with overlap. Good enough for demo KB."""
    if not text:
        return []
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + chunk_size)
        # try to break at a sentence boundary within the last 200 chars
        if end < n:
            back = text.rfind(". ", max(start, end - 300), end)
            if back != -1 and back - start > 400:
                end = back + 2
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--filings", default="/tmp/demo-filings")
    ap.add_argument("--bucket", required=True, help="ChunksBucket name")
    ap.add_argument("--prefix", default="kb-chunks/")
    args = ap.parse_args()

    src = Path(args.filings)
    manifest_path = src / "manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: manifest not found at {manifest_path}")
        sys.exit(1)

    manifest = json.loads(manifest_path.read_text())
    s3 = boto3.client("s3", region_name=REGION)

    total_chunks = 0
    total_files = 0
    for entry in manifest:
        ticker = entry["ticker"]
        form = entry["form"]
        filing_date = entry["filing_date"]
        url = entry["url"]
        accession = entry["accession"]
        file_path = Path(entry["file"])
        if not file_path.exists():
            print(f"[skip] {ticker} missing file {file_path}")
            continue

        html = file_path.read_bytes()
        print(f"[parse] {ticker} {form} bytes={len(html):,}", flush=True)
        text = html_to_text(html)
        print(f"        cleaned_chars={len(text):,}", flush=True)
        chunks = chunk_text(text)
        # Cap chunks per filing to keep upload time + KB index size in check
        # while still giving the retrieval side real, meaningful coverage.
        MAX_CHUNKS_PER_FILING = 60
        if len(chunks) > MAX_CHUNKS_PER_FILING:
            # Keep a spread of chunks: first few (cover summary/MD&A), middle (body),
            # last few (risk factors often live there).
            keep = (
                chunks[:30]
                + chunks[len(chunks) // 2 - 10 : len(chunks) // 2 + 10]
                + chunks[-10:]
            )
            chunks = keep
        print(f"        chunks_kept={len(chunks)}", flush=True)

        def _put_one(idx_chunk):
            idx, chunk = idx_chunk
            source_chunk_id = f"{ticker}-{accession.replace('-','')}-c{idx:04d}"
            body = {
                "text": chunk,
                "metadata": {
                    "ticker": ticker,
                    "form": form,
                    "filing_date": filing_date,
                    "accession": accession,
                    "chunk_index": idx,
                    "source_url": url,
                    "source_chunk_id": source_chunk_id,
                },
            }
            key = f"{args.prefix}{source_chunk_id}.json"
            s3.put_object(
                Bucket=args.bucket,
                Key=key,
                Body=json.dumps(body).encode("utf-8"),
                ContentType="application/json",
            )
            return source_chunk_id

        with ThreadPoolExecutor(max_workers=16) as pool:
            futures = [pool.submit(_put_one, (i, c)) for i, c in enumerate(chunks)]
            for f in as_completed(futures):
                f.result()
                total_chunks += 1
        total_files += 1
        print(f"[ok] {ticker} uploaded {len(chunks)} chunks", flush=True)

    print(f"\n--- total_files={total_files} total_chunks={total_chunks} bucket={args.bucket} prefix={args.prefix} ---")


if __name__ == "__main__":
    main()
