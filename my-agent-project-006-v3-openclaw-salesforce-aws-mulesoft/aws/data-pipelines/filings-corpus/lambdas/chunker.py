"""Section-aware 10-K / 10-Q chunker.

Standard recursive text-splitters destroy the semantic boundaries that make
SEC filings useful. A "Risk Factors" chunk that spills into "Unresolved Staff
Comments" is a retrieval disaster - the reader expects risk language, the
retriever serves them disclosure boilerplate.

This chunker:
  1. splits the document on known Item / Part boundaries
  2. within each section, splits on paragraph boundaries up to max_tokens
  3. preserves section name on every chunk as metadata
  4. never splits a sentence in half (sliding boundary on ". ")

Output is a list of dicts compatible with Bedrock KB ingestion format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 10-K item titles (per SEC Form 10-K); order matters - longer first.
TENK_ITEMS: list[str] = [
    "Item 1. Business",
    "Item 1A. Risk Factors",
    "Item 1B. Unresolved Staff Comments",
    "Item 1C. Cybersecurity",
    "Item 2. Properties",
    "Item 3. Legal Proceedings",
    "Item 4. Mine Safety Disclosures",
    "Item 5. Market for Registrant's Common Equity",
    "Item 6. Reserved",
    "Item 7. Management's Discussion and Analysis",
    "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
    "Item 8. Financial Statements and Supplementary Data",
    "Item 9. Changes in and Disagreements With Accountants",
    "Item 9A. Controls and Procedures",
    "Item 9B. Other Information",
    "Item 10. Directors, Executive Officers and Corporate Governance",
    "Item 11. Executive Compensation",
    "Item 12. Security Ownership",
    "Item 13. Certain Relationships and Related Transactions",
    "Item 14. Principal Accountant Fees and Services",
    "Item 15. Exhibits, Financial Statement Schedules",
]

# 10-Q parts (shorter, simpler layout).
TENQ_PARTS: list[str] = [
    "Part I. Financial Information",
    "Item 1. Financial Statements",
    "Item 2. Management's Discussion and Analysis",
    "Item 3. Quantitative and Qualitative Disclosures",
    "Item 4. Controls and Procedures",
    "Part II. Other Information",
    "Item 1. Legal Proceedings",
    "Item 1A. Risk Factors",
    "Item 2. Unregistered Sales of Equity Securities",
    "Item 3. Defaults Upon Senior Securities",
    "Item 4. Mine Safety Disclosures",
    "Item 5. Other Information",
    "Item 6. Exhibits",
]


@dataclass(frozen=True)
class Chunk:
    text: str
    section: str
    order: int
    form: str
    cik: str
    accession: str


def _pick_sections(form: str) -> list[str]:
    if form == "10-K":
        return TENK_ITEMS
    if form == "10-Q":
        return TENQ_PARTS
    return []


def _split_on_sections(text: str, sections: list[str]) -> list[tuple[str, str]]:
    """Return [(section_title, body)]. Body may be empty."""
    if not sections:
        return [("Full Document", text)]
    pattern = "|".join(re.escape(s) for s in sections)
    parts = re.split(f"(?={pattern})", text, flags=re.IGNORECASE)
    out: list[tuple[str, str]] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        header = p.splitlines()[0].strip()
        matched = next(
            (s for s in sections if header.lower().startswith(s.lower())), "Front Matter"
        )
        body = p[len(header):].strip() if matched != "Front Matter" else p
        out.append((matched, body))
    return out


def _split_body(body: str, max_tokens: int = 450) -> list[str]:
    """Split body on paragraph then sentence boundary, respecting a rough token cap.

    Token cap is approximate (4 chars ≈ 1 token); we do not tokenize with a
    real tokenizer here to keep this Lambda light. The embedder enforces the
    strict 512-token Titan v2 limit downstream.
    """
    max_chars = max_tokens * 4
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", body) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        if len(buf) + len(p) + 2 <= max_chars:
            buf = (buf + "\n\n" + p).strip()
            continue
        if buf:
            chunks.append(buf)
            buf = ""
        if len(p) <= max_chars:
            buf = p
            continue
        # Paragraph still too long: break on sentence boundary.
        sentences = re.split(r"(?<=[.!?])\s+", p)
        sent_buf = ""
        for s in sentences:
            if len(sent_buf) + len(s) + 1 <= max_chars:
                sent_buf = (sent_buf + " " + s).strip()
            else:
                if sent_buf:
                    chunks.append(sent_buf)
                sent_buf = s
        if sent_buf:
            buf = sent_buf
    if buf:
        chunks.append(buf)
    return chunks


def chunk_filing(text: str, *, form: str, cik: str, accession: str) -> list[Chunk]:
    """Public API. Strip HTML upstream; feed plain text in."""
    sections = _pick_sections(form)
    out: list[Chunk] = []
    order = 0
    for section, body in _split_on_sections(text, sections):
        for piece in _split_body(body):
            out.append(
                Chunk(
                    text=piece,
                    section=section,
                    order=order,
                    form=form,
                    cik=cik,
                    accession=accession,
                )
            )
            order += 1
    return out
