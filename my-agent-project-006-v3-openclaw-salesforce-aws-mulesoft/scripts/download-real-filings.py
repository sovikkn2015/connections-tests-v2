#!/usr/bin/env python3
"""Pull real 10-Q / 10-K primary documents from SEC EDGAR for the demo KB.

Discovery flow: SEC data.sec.gov/submissions/CIK########.json → most recent
10-Q or 10-K → Archives filing directory → primary document filename. This
resolves URLs dynamically so we never ship stale hardcoded links.

Output: {ticker}-{form}.htm files plus a manifest.json with
metadata (cik, accession, filing_date, primary_doc).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests  # type: ignore[import-untyped]

UA = "OpenClawV3 demo-ingestor demo@openclaw.ai"

COMPANIES = [
    ("NVDA", "0001045810"),
    ("MSFT", "0000789019"),
    ("AAPL", "0000320193"),
    ("TSLA", "0001318605"),
    ("META", "0001326801"),
    ("GOOGL", "0001652044"),
    ("AMZN", "0001018724"),
    ("AMD", "0000002488"),
    ("JPM", "0000019617"),
    ("GS", "0000886982"),
]

WANTED_FORMS = ("10-Q", "10-K")


_session = requests.Session()
_session.headers.update({"User-Agent": UA, "Accept": "*/*"})


def http_get(url: str) -> bytes:
    r = _session.get(url, timeout=30)
    r.raise_for_status()
    return r.content


def find_latest(cik: str) -> dict | None:
    """Resolve most recent 10-Q or 10-K filing metadata for a CIK."""
    cik_padded = cik.zfill(10)
    sub_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    data = json.loads(http_get(sub_url))
    recent = data["filings"]["recent"]
    forms = recent["form"]
    acc_numbers = recent["accessionNumber"]
    primary_docs = recent["primaryDocument"]
    filing_dates = recent["filingDate"]
    for i, form in enumerate(forms):
        if form in WANTED_FORMS:
            return {
                "form": form,
                "accession": acc_numbers[i],
                "primary_doc": primary_docs[i],
                "filing_date": filing_dates[i],
                "cik": cik.lstrip("0") or "0",
            }
    return None


def build_doc_url(cik: str, accession: str, primary_doc: str) -> str:
    cik_int = str(int(cik))
    acc_nodash = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nodash}/{primary_doc}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/demo-filings")
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    ok = 0
    fail = 0
    for ticker, cik in COMPANIES:
        try:
            meta = find_latest(cik)
            if not meta:
                print(f"[none] {ticker}: no recent 10-Q or 10-K")
                fail += 1
                continue
            url = build_doc_url(meta["cik"], meta["accession"], meta["primary_doc"])
            body = http_get(url)
            fname = f"{ticker}-{meta['form']}-{meta['filing_date']}.htm"
            out_path = out_dir / fname
            out_path.write_bytes(body)
            manifest.append(
                {
                    "ticker": ticker,
                    "cik": meta["cik"],
                    "form": meta["form"],
                    "filing_date": meta["filing_date"],
                    "accession": meta["accession"],
                    "primary_doc": meta["primary_doc"],
                    "url": url,
                    "bytes": len(body),
                    "file": str(out_path),
                }
            )
            print(f"[ok]   {ticker} {meta['form']} {meta['filing_date']} bytes={len(body):,}")
            ok += 1
            time.sleep(0.35)  # EDGAR fair-use
        except Exception as exc:  # noqa: BLE001
            print(f"[fail] {ticker}: {type(exc).__name__}: {exc}")
            fail += 1
            time.sleep(0.5)

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n--- ok={ok} fail={fail} out={out_dir} ---")
    if ok == 0:
        sys.exit(2)


if __name__ == "__main__":
    main()
