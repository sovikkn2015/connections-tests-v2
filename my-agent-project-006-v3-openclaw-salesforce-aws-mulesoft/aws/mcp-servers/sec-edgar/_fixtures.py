"""Mock fixtures for the sec-edgar MCP server.

Used by ``app.py`` when ``SEC_EDGAR_MODE=mock`` (the default for unit tests
and local dev). Three groups:

- ``MOCK_10K_FILING_TEXT`` — a few paragraphs of realistic-looking 10-K
  prose; source material for ``MOCK_SOURCE_CHUNKS`` excerpts so drift
  stays contained in one place.
- ``MOCK_SOURCE_TABLES`` — pre-indexed ``SourceTable`` payloads keyed by
  ``source_id`` (pattern ``<cik>-<accession>-tab-<n>``). Matches the
  shape frontend/src/types/api.ts::SourceTable.
- ``MOCK_SOURCE_CHUNKS`` — pre-indexed ``SourceChunk`` payloads keyed by
  ``source_id`` (pattern ``<cik>-<accession>-chunk-<n>``). Matches the
  shape frontend/src/types/api.ts::SourceChunk.

Live mode (``SEC_EDGAR_MODE=live``) will resolve ``source_id`` against
the Bedrock KB metadata catalog once the filings-corpus catalog build
ships. Until then live mode returns empty stubs (see handler docstrings).
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 10-K prose source — the MOCK_SOURCE_CHUNKS below excerpt from this body
# so the two fixture groups stay internally consistent.
# ---------------------------------------------------------------------------
MOCK_10K_FILING_TEXT = """\
Item 1A. Risk Factors

Our results depend on continued demand for accelerated computing. The market
for AI accelerators has grown rapidly, and a material portion of our revenue
is concentrated in a small number of hyperscale cloud customers. A reduction
in orders from any of these customers, or a shift in their capital expenditure
cadence, could materially affect our quarterly results.

Supply chain concentration in Asia-Pacific subjects us to geopolitical risk.
Export control regulations targeting advanced semiconductors have impacted
revenue in China. Further tightening of these regulations, or retaliatory
action, could restrict our addressable market.

Item 7. Management's Discussion and Analysis of Financial Condition

Data center revenue grew year-over-year driven by continued adoption of
generative AI workloads. Gross margin expanded due to favorable product mix
and ongoing manufacturing efficiencies. Operating expenses rose as we
invested in R&D for next-generation architectures and expanded our software
platform offerings.

Cash provided by operating activities increased meaningfully year-over-year,
reflecting strong earnings and working capital improvements. We returned
capital to stockholders through share repurchases and ongoing dividends,
while maintaining investment capacity for strategic acquisitions.
"""


# ---------------------------------------------------------------------------
# SourceTable fixtures — keyed by source_id. Shape mirrors
# frontend/src/types/api.ts::SourceTable.
# ---------------------------------------------------------------------------
MOCK_SOURCE_TABLES: dict[str, dict] = {
    "nvda-0001045810-24-000316-tab-1": {
        "source_id": "nvda-0001045810-24-000316-tab-1",
        "title": "NVIDIA segment revenue — FY2024 10-K",
        "columns": ["Segment", "FY2024", "FY2023", "YoY %"],
        "rows": [
            {
                "key": "data_center",
                "label": "Data Center",
                "values": {"FY2024": 47525, "FY2023": 15005, "YoY %": 217.0},
            },
            {
                "key": "gaming",
                "label": "Gaming",
                "values": {"FY2024": 10447, "FY2023": 9067, "YoY %": 15.2},
            },
            {
                "key": "professional_viz",
                "label": "Professional Visualization",
                "values": {"FY2024": 1553, "FY2023": 1544, "YoY %": 0.6},
            },
            {
                "key": "automotive",
                "label": "Automotive",
                "values": {"FY2024": 1091, "FY2023": 903, "YoY %": 20.8},
            },
        ],
        "as_of": "2024-FY",
        "citation": {
            "span_id": "nvda-10k-2024-seg",
            "source_id": "nvda-0001045810-24-000316-tab-1",
            "source_type": "filing",
            "label": "NVDA FY2024 10-K, Segment Revenue",
            "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000316/nvda-10k.htm",
        },
    },
    "aapl-0000320193-24-000123-tab-1": {
        "source_id": "aapl-0000320193-24-000123-tab-1",
        "title": "Apple net sales by product — FY2024 10-K",
        "columns": ["Category", "FY2024", "FY2023", "YoY %"],
        "rows": [
            {
                "key": "iphone",
                "label": "iPhone",
                "values": {"FY2024": 201183, "FY2023": 200583, "YoY %": 0.3},
            },
            {
                "key": "services",
                "label": "Services",
                "values": {"FY2024": 96169, "FY2023": 85200, "YoY %": 12.9},
            },
            {
                "key": "wearables",
                "label": "Wearables, Home & Accessories",
                "values": {"FY2024": 37005, "FY2023": 39845, "YoY %": -7.1},
            },
            {
                "key": "mac",
                "label": "Mac",
                "values": {"FY2024": 29984, "FY2023": 29357, "YoY %": 2.1},
            },
        ],
        "as_of": "2024-FY",
        "citation": {
            "span_id": "aapl-10k-2024-prod",
            "source_id": "aapl-0000320193-24-000123-tab-1",
            "source_type": "filing",
            "label": "AAPL FY2024 10-K, Net Sales by Category",
            "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-10k.htm",
        },
    },
    "amd-0000002488-24-000089-tab-1": {
        "source_id": "amd-0000002488-24-000089-tab-1",
        "title": "AMD segment operating income — FY2024 10-K",
        "columns": ["Segment", "FY2024", "FY2023", "YoY %"],
        "rows": [
            {
                "key": "data_center",
                "label": "Data Center",
                "values": {"FY2024": 3481, "FY2023": 1267, "YoY %": 174.7},
            },
            {
                "key": "client",
                "label": "Client",
                "values": {"FY2024": 897, "FY2023": 46, "YoY %": 1849.0},
            },
            {
                "key": "gaming",
                "label": "Gaming",
                "values": {"FY2024": 280, "FY2023": 971, "YoY %": -71.2},
            },
            {
                "key": "embedded",
                "label": "Embedded",
                "values": {"FY2024": 1321, "FY2023": 2628, "YoY %": -49.7},
            },
        ],
        "as_of": "2024-FY",
        "citation": {
            "span_id": "amd-10k-2024-seg-oi",
            "source_id": "amd-0000002488-24-000089-tab-1",
            "source_type": "filing",
            "label": "AMD FY2024 10-K, Segment Operating Income",
            "url": "https://www.sec.gov/Archives/edgar/data/2488/000000248824000089/amd-10k.htm",
        },
    },
}


# ---------------------------------------------------------------------------
# SourceChunk fixtures — keyed by source_id. Shape mirrors
# frontend/src/types/api.ts::SourceChunk.
# ---------------------------------------------------------------------------
MOCK_SOURCE_CHUNKS: dict[str, dict] = {
    "nvda-0001045810-24-000316-chunk-1": {
        "source_id": "nvda-0001045810-24-000316-chunk-1",
        "title": "NVIDIA FY2024 10-K — Item 1A. Risk Factors (customer concentration)",
        "filing_type": "10-K",
        "filing_date": "2024-02-21",
        "section": "Item 1A. Risk Factors",
        "page": 17,
        "text": (
            "Our results depend on continued demand for accelerated computing. "
            "The market for AI accelerators has grown rapidly, and a material "
            "portion of our revenue is concentrated in a small number of "
            "hyperscale cloud customers. A reduction in orders from any of "
            "these customers, or a shift in their capital expenditure cadence, "
            "could materially affect our quarterly results."
        ),
        "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000316/nvda-10k.htm",
    },
    "nvda-0001045810-24-000316-chunk-2": {
        "source_id": "nvda-0001045810-24-000316-chunk-2",
        "title": "NVIDIA FY2024 10-K — Item 1A. Risk Factors (geopolitical)",
        "filing_type": "10-K",
        "filing_date": "2024-02-21",
        "section": "Item 1A. Risk Factors",
        "page": 19,
        "text": (
            "Supply chain concentration in Asia-Pacific subjects us to "
            "geopolitical risk. Export control regulations targeting advanced "
            "semiconductors have impacted revenue in China. Further tightening "
            "of these regulations, or retaliatory action, could restrict our "
            "addressable market."
        ),
        "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000316/nvda-10k.htm",
    },
    "nvda-0001045810-24-000316-chunk-3": {
        "source_id": "nvda-0001045810-24-000316-chunk-3",
        "title": "NVIDIA FY2024 10-K — Item 7. MD&A (data center)",
        "filing_type": "10-K",
        "filing_date": "2024-02-21",
        "section": "Item 7. Management's Discussion and Analysis",
        "page": 42,
        "text": (
            "Data center revenue grew year-over-year driven by continued "
            "adoption of generative AI workloads. Gross margin expanded due "
            "to favorable product mix and ongoing manufacturing efficiencies. "
            "Operating expenses rose as we invested in R&D for next-generation "
            "architectures and expanded our software platform offerings."
        ),
        "url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000316/nvda-10k.htm",
    },
    "aapl-0000320193-24-000123-chunk-1": {
        "source_id": "aapl-0000320193-24-000123-chunk-1",
        "title": "Apple FY2024 10-K — Services segment commentary",
        "filing_type": "10-K",
        "filing_date": "2024-11-01",
        "section": "Item 7. Management's Discussion and Analysis",
        "page": 28,
        "text": (
            "Services net sales grew year-over-year across substantially all "
            "categories, driven by advertising, cloud services, and the App "
            "Store. The Company continues to expect its installed base of "
            "active devices to be an important driver of future Services "
            "growth."
        ),
        "url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-10k.htm",
    },
    "amd-0000002488-24-000089-chunk-1": {
        "source_id": "amd-0000002488-24-000089-chunk-1",
        "title": "AMD FY2024 10-K — Data Center segment",
        "filing_type": "10-K",
        "filing_date": "2024-02-27",
        "section": "Item 7. Management's Discussion and Analysis",
        "page": 35,
        "text": (
            "Data Center segment revenue increased significantly year-over-"
            "year, driven by strong demand for our Instinct accelerators and "
            "EPYC server processors. We expect continued momentum as customers "
            "deploy AI training and inference infrastructure at scale."
        ),
        "url": "https://www.sec.gov/Archives/edgar/data/2488/000000248824000089/amd-10k.htm",
    },
}


def empty_source_table(source_id: str) -> dict:
    """Fallback shape when ``source_id`` is not in ``MOCK_SOURCE_TABLES``."""
    return {
        "source_id": source_id,
        "title": "(source not available)",
        "columns": [],
        "rows": [],
        "as_of": "",
        "citation": {
            "span_id": "",
            "source_id": source_id,
            "source_type": "filing",
            "label": "(unavailable)",
        },
    }


def empty_source_chunk(source_id: str) -> dict:
    """Fallback shape when ``source_id`` is not in ``MOCK_SOURCE_CHUNKS``."""
    return {
        "source_id": source_id,
        "title": "(source not available)",
        "text": "",
    }
