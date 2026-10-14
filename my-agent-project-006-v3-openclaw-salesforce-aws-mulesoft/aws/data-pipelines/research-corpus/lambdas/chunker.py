"""Lightweight memo chunker for research_memo.Body__c.

Memos are much smaller than 10-K filings (~1-5k words), so we skip the
section-aware logic and use a paragraph + sentence recursive splitter
with a fixed max-tokens cap of ~450.
"""

from __future__ import annotations

import re

MAX_TOKENS = 450
MAX_CHARS = MAX_TOKENS * 4


def chunk_memo(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    out: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 <= MAX_CHARS:
            buf = (buf + "\n\n" + p).strip()
            continue
        if buf:
            out.append(buf)
            buf = ""
        if len(p) <= MAX_CHARS:
            buf = p
            continue
        # Very long paragraph: break on sentence boundary
        sentences = re.split(r"(?<=[.!?])\s+", p)
        sbuf = ""
        for s in sentences:
            if len(sbuf) + len(s) + 1 <= MAX_CHARS:
                sbuf = (sbuf + " " + s).strip()
            else:
                if sbuf:
                    out.append(sbuf)
                sbuf = s
        if sbuf:
            buf = sbuf
    if buf:
        out.append(buf)
    return out
