#!/usr/bin/env bash
# Download a handful of recent 10-Q filings for the demo KB.
# Zero credentials. EDGAR requires a User-Agent header.
set -e

UA="OpenClawV3 demo@openclaw.ai"
OUT="${1:-/tmp/demo-filings}"
mkdir -p "$OUT"

download_one() {
  local ticker="$1"
  local url="$2"
  local out="$OUT/${ticker}-10Q.html"
  if [ -s "$out" ]; then
    echo "[cached] $ticker"
    return 0
  fi
  echo "[fetch] $ticker"
  if curl -sSL -A "$UA" -o "$out" "$url"; then
    local size
    size=$(wc -c < "$out" | tr -d ' ')
    echo "[done] $ticker size=$size"
  else
    echo "[FAIL] $ticker"
    rm -f "$out"
  fi
  sleep 0.3
}

download_one NVDA  "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000316/nvda-20240728.htm"
download_one MSFT  "https://www.sec.gov/Archives/edgar/data/789019/000095017024087843/msft-20240630.htm"
download_one AAPL  "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240629.htm"
download_one TSLA  "https://www.sec.gov/Archives/edgar/data/1318605/000162828024032002/tsla-20240630.htm"
download_one META  "https://www.sec.gov/Archives/edgar/data/1326801/000132680124000084/meta-20240630.htm"
download_one GOOGL "https://www.sec.gov/Archives/edgar/data/1652044/000165204424000097/goog-20240630.htm"
download_one AMZN  "https://www.sec.gov/Archives/edgar/data/1018724/000101872424000115/amzn-20240630.htm"
download_one AMD   "https://www.sec.gov/Archives/edgar/data/2488/000000248824000118/amd-20240629.htm"
download_one JPM   "https://www.sec.gov/Archives/edgar/data/19617/000001961724000473/jpm-20240630.htm"
download_one GS    "https://www.sec.gov/Archives/edgar/data/886982/000088698224000074/gs-20240630.htm"

echo ""
echo "--- summary ---"
ls -la "$OUT" | head -20
