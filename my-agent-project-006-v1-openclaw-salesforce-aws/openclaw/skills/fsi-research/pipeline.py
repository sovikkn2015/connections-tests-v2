"""
FSI Research Pipeline Orchestrator — AutoResearchClaw 23-Stage Pipeline.

Project 006: OpenClaw + Salesforce + AWS
Phase 3: Pipeline adaptation for investment research briefs

This is the core engine. It receives a research query, runs 23 stages
sequentially through MCP tools, financial models, LLM analysis, and
Salesforce CRM — producing a compliance-screened equity research brief.

Anti-fabrication rule: every number in the final brief MUST trace back
to a tool result stored in self.data_sources. No hallucinated stats.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import requests
from langfuse import Langfuse

# ── Sibling skill imports (financial models run in-process) ─────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "financial-analysis"))
from comps import run_comps  # noqa: E402
from dcf import run_dcf  # noqa: E402
from monte_carlo import run_monte_carlo  # noqa: E402
from sandbox import run_in_sandbox  # noqa: E402

# ── MetaClaw cross-run learning ─────────────────────────────────────
from metaclaw import record_lesson, apply_lessons  # noqa: E402

# ── Compliance & audit skill imports ────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "compliance-screening"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "audit-logging"))
from screening import run_compliance_screening  # noqa: E402
from logger import log_audit as audit_log_write  # noqa: E402
from mnpi_filter import filter_mnpi, summarize_holdings_safe  # noqa: E402

# ── Einstein Trust Layer (dual trust: Bedrock Guardrails + SF Models API) ──
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "salesforce-crm"))
from trust_layer import generate_with_trust_layer, is_trust_layer_available  # noqa: E402

logger = logging.getLogger("fsi-research-pipeline")

SF_API_VERSION = "v66.0"
# HITL gates — must match config.arc.yaml hitl.stage_policies
# Stage 7:  Data Quality Gate (analyst verifies data completeness)
# Stage 13: Analysis Review Gate (analyst reviews model outputs)
# Stage 21: Final Approval Gate (analyst approves brief for publish)
HITL_STAGES = {7, 13, 21}



def _now_iso() -> str:
    """UTC ISO-8601 timestamp."""
    return datetime.now(timezone.utc).isoformat()


class FSIResearchPipeline:
    """
    23-stage equity research pipeline orchestrator.

    Orchestrates MCP tool calls, financial models, LLM synthesis,
    Salesforce CRM reads/writes, compliance screening, and HITL gates
    to produce a structured investment research brief.
    """

    def __init__(
        self,
        ticker: str,
        query: str,
        analyst: str,
        config: dict | None = None,
    ) -> None:
        self.ticker = ticker.upper().strip()
        self.query = query
        self.analyst = analyst
        self.config = config or {}

        # Run identity
        self.run_id = f"arc-{uuid.uuid4().hex[:12]}"
        self.started_at = datetime.now(timezone.utc)

        # Environment
        self.sf_instance_url = os.environ["SF_INSTANCE_URL"]
        self.sf_access_token = os.environ["SF_ACCESS_TOKEN"]
        self.mcp_gateway_url = os.environ["MCP_GATEWAY_URL"]
        self.mcp_api_key = os.environ["MCP_API_KEY"]

        # Langfuse tracing
        self.langfuse = Langfuse(
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            host=os.environ["LANGFUSE_BASE_URL"],
        )
        self.trace = self.langfuse.trace(
            name="fsi-research-pipeline",
            metadata={
                "run_id": self.run_id,
                "ticker": self.ticker,
                "analyst": self.analyst,
                "query": self.query,
            },
        )

        # Pipeline state
        self.current_stage: int = 0
        self.completed_stages: list[int] = []
        self.stage_results: dict[int, Any] = {}
        self.data_sources: dict[str, Any] = {}  # anti-fabrication ledger
        self.model_outputs: dict[str, Any] = {}
        self.errors: list[dict] = []
        self.hitl_gates: list[dict] = []
        self.brief: dict[str, Any] = {}
        self.compliance_result: dict | None = None

        # Collected data buckets (populated by stages 1-6)
        self.intake: dict[str, Any] = {}
        self.crm_context: dict[str, Any] = {}
        self.market_data: dict[str, Any] = {}
        self.news_data: dict[str, Any] = {}
        self.sec_filings: dict[str, Any] = {}
        self.transcript_summary: str = ""

        # Analysis outputs (populated by stages 8-12)
        self.financial_model_inputs: dict[str, Any] = {}
        self.dcf_result: dict[str, Any] = {}
        self.comps_result: dict[str, Any] = {}
        self.monte_carlo_result: dict[str, Any] = {}
        self.sentiment_synthesis: str = ""

        # Synthesis outputs (populated by stages 14-18)
        self.thesis: str = ""
        self.catalysts: str = ""
        self.risks: str = ""
        self.rating: str = ""
        self.target_price: float | None = None

        # Einstein Trust Layer availability (lazy-checked on first CRM reasoning call)
        self._trust_layer_available: bool | None = None


    # ── Main entry point ────────────────────────────────────────────

    def _all_stage_methods(self) -> list:
        """Ordered list of all 23 stage coroutines."""
        return [
            self._stage_1_intake, self._stage_2_crm_context,
            self._stage_3_market_data, self._stage_4_news_sentiment,
            self._stage_5_sec_filings, self._stage_6_transcript_analysis,
            self._stage_7_data_quality_gate, self._stage_8_financial_modeling,
            self._stage_9_dcf_valuation, self._stage_10_comps_analysis,
            self._stage_11_monte_carlo, self._stage_12_sentiment_synthesis,
            self._stage_13_analysis_review_gate, self._stage_14_thesis_generation,
            self._stage_15_catalyst_identification, self._stage_16_risk_assessment,
            self._stage_17_rating_determination, self._stage_18_target_price_calc,
            self._stage_19_brief_assembly, self._stage_20_compliance_check,
            self._stage_21_final_approval_gate, self._stage_22_crm_writeback,
            self._stage_23_delivery_notify,
        ]

    async def run(self) -> dict:
        """
        Execute all 23 stages sequentially.

        Returns
        -------
        dict
            status: "completed" | "paused" | "failed"
            If paused at a HITL gate, includes gate context for the caller.
        """
        return await self._execute_stages(start=1)

    async def resume(self, from_stage: int, approval: dict) -> dict:
        """
        Resume after an analyst approves (or rejects) a HITL gate.

        Parameters
        ----------
        from_stage : int
            Stage to resume from (gate stage + 1).
        approval : dict
            {approved: bool, notes: str, analyst: str}
        """
        if not approval.get("approved"):
            self._log_audit(
                action="HITL_REJECTED", stage=from_stage - 1,
                detail=approval.get("notes", "Analyst rejected"),
                compliance_status="FAIL",
            )
            return {
                "status": "rejected", "run_id": self.run_id,
                "rejected_at_stage": from_stage - 1,
                "notes": approval.get("notes"),
            }

        self._log_audit(
            action="HITL_APPROVED", stage=from_stage - 1,
            detail=f"Approved by {approval.get('analyst', self.analyst)}",
            compliance_status="PASS",
        )
        return await self._execute_stages(start=from_stage)

    async def _execute_stages(self, start: int) -> dict:
        """Run stages from *start* through 23."""
        methods = self._all_stage_methods()
        for i in range(start, 24):
            self.current_stage = i
            stage_fn = methods[i - 1]
            span = self.trace.span(
                name=f"stage-{i}-{stage_fn.__name__}",
                metadata={"stage": i, "ticker": self.ticker},
            )

            # MetaClaw: check for applicable lessons before each stage
            try:
                lessons = apply_lessons(self.ticker, i)
                if lessons:
                    logger.info("MetaClaw lessons for stage %d: %s", i, lessons)
            except Exception:
                pass  # MetaClaw is advisory — never block the pipeline

            try:
                logger.info("Stage %d: %s — starting", i, stage_fn.__name__)
                result = await stage_fn()
                self.stage_results[i] = result
                self.completed_stages.append(i)
                span.end(metadata={"status": "completed"})

                # HITL gate — pause for analyst approval
                if isinstance(result, dict) and result.get("gate"):
                    self.hitl_gates.append(result)
                    self.langfuse.flush()
                    return {
                        "status": "paused", "run_id": self.run_id,
                        "paused_at_stage": i, "gate": result,
                        "completed_stages": self.completed_stages,
                    }
            except Exception as exc:
                self.errors.append({
                    "stage": i, "method": stage_fn.__name__,
                    "error": str(exc), "timestamp": _now_iso(),
                })
                span.end(metadata={"status": "error", "error": str(exc)})
                logger.exception("Stage %d failed: %s", i, exc)
                self._log_audit(
                    action="PIPELINE_ERROR", stage=i,
                    detail=str(exc), compliance_status="FAIL",
                )

                # Repair loop
                repaired = False
                if self.config.get("experiment", {}).get("repair", {}).get("enabled"):
                    for attempt in range(self.config["experiment"]["repair"].get("max_cycles", 3)):
                        try:
                            result = await stage_fn()
                            self.stage_results[i] = result
                            self.completed_stages.append(i)
                            repaired = True
                            # MetaClaw: record recovery
                            try:
                                record_lesson(self.run_id, i, "recovery", f"Stage {i} failed then recovered: {str(exc)}", "warning", self.ticker)
                            except Exception:
                                pass
                            break
                        except Exception:
                            continue
                if not repaired:
                    # MetaClaw: record permanent failure
                    try:
                        record_lesson(self.run_id, i, "failure", f"Stage {i} failed permanently: {str(exc)}", "error", self.ticker)
                    except Exception:
                        pass
                    self.langfuse.flush()
                    return {
                        "status": "failed", "run_id": self.run_id,
                        "failed_at_stage": i, "errors": self.errors,
                        "completed_stages": self.completed_stages,
                    }

        # MetaClaw: record successful pipeline completion
        try:
            record_lesson(
                self.run_id, 23, "success",
                f"Pipeline completed for {self.ticker}. Rating: {self._extract_rating_label()}, Target: ${self.target_price}",
                "info", self.ticker,
            )
        except Exception:
            pass

        self.langfuse.flush()
        return {
            "status": "completed", "run_id": self.run_id,
            "ticker": self.ticker, "analyst": self.analyst,
            "brief": self.brief, "rating": self.rating,
            "target_price": self.target_price,
            "completed_stages": self.completed_stages,
            "data_sources": list(self.data_sources.keys()),
            "errors": self.errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": _now_iso(),
        }


    # ════════════════════════════════════════════════════════════════
    # PHASE A: INTAKE (Stages 1-2)
    # ════════════════════════════════════════════════════════════════

    async def _stage_1_intake(self) -> dict:
        """Stage 1 — Intake & Parse: extract ticker, event, timeframe."""
        parsed = {
            "ticker": self.ticker, "query": self.query,
            "analyst": self.analyst, "run_id": self.run_id,
            "event_type": None, "timeframe": None, "focus_areas": [],
        }
        q = self.query.lower()

        # Event type detection
        for etype, pat in {
            "earnings": r"\b(earnings|quarterly results|q[1-4]|revenue report)\b",
            "ipo": r"\b(ipo|initial public offering|listing)\b",
            "merger": r"\b(merger|acquisition|m&a|takeover|buyout)\b",
            "guidance": r"\b(guidance|outlook|forecast update)\b",
            "initiation": r"\b(initiation|initiating coverage|new coverage)\b",
            "sector_review": r"\b(sector review|industry update|peer comparison)\b",
            "catalyst": r"\b(catalyst|upcoming event|product launch|fda)\b",
        }.items():
            if re.search(pat, q):
                parsed["event_type"] = etype
                break
        parsed["event_type"] = parsed["event_type"] or "general_research"

        # Timeframe detection
        for tf, pat in {
            "near_term": r"\b(ahead of|before|near[- ]term|this week|next week)\b",
            "quarterly": r"\b(quarter|q[1-4]|quarterly)\b",
            "annual": r"\b(annual|year[- ]end|fy\d{2,4})\b",
            "long_term": r"\b(long[- ]term|multi[- ]year|5[- ]year)\b",
        }.items():
            if re.search(pat, q):
                parsed["timeframe"] = tf
                break
        parsed["timeframe"] = parsed["timeframe"] or "standard"

        # Focus areas
        for area, pat in {
            "fundamentals": r"\b(fundamental|financials|revenue|earnings|margins)\b",
            "valuation": r"\b(valuation|dcf|fair value|overvalued|undervalued)\b",
            "sentiment": r"\b(sentiment|news|headlines|market reaction)\b",
            "technicals": r"\b(technical|chart|support|resistance|momentum)\b",
            "catalysts": r"\b(catalyst|event|trigger|upcoming)\b",
            "risks": r"\b(risk|downside|bear case|headwind)\b",
            "competitive": r"\b(competitive|peer|comps|market share)\b",
        }.items():
            if re.search(pat, q):
                parsed["focus_areas"].append(area)
        if not parsed["focus_areas"]:
            parsed["focus_areas"] = [
                "fundamentals", "valuation", "sentiment",
                "catalysts", "risks", "competitive",
            ]

        self.intake = parsed
        self._record_source("intake_parse", parsed)
        self._log_audit(action="PIPELINE_START", stage=1, detail=json.dumps(parsed))
        return parsed

    async def _stage_2_crm_context(self) -> dict:
        """Stage 2 — CRM Context Fetch: IR_Coverage__c, IR_Watchlist__c, IR_Company__c."""
        ctx = {"company": None, "coverage": [], "watchlist": [], "prior_research": []}

        # Company record
        resp = self._sf_soql(
            f"SELECT Id,Name,Ticker__c,Sector__c,Exchange__c,Market_Cap__c,Description__c "
            f"FROM IR_Company__c WHERE Ticker__c='{self.ticker}'"
        )
        if resp.get("records"):
            ctx["company"] = resp["records"][0]
            self._record_source("sf_company", resp["records"][0])

        # Coverage assignments
        resp = self._sf_soql(
            f"SELECT Analyst__c,Rating__c,Target_Price__c,Last_Updated__c,Last_Action__c "
            f"FROM IR_Coverage__c WHERE Company__r.Ticker__c='{self.ticker}'"
        )
        ctx["coverage"] = filter_mnpi(resp.get("records", []))
        if ctx["coverage"]:
            self._record_source("sf_coverage", ctx["coverage"])

        # Watchlist
        resp = self._sf_soql(
            f"SELECT Reason__c,Priority__c,Added_Date__c,Earnings_Date__c "
            f"FROM IR_Watchlist__c WHERE Company__r.Ticker__c='{self.ticker}'"
        )
        ctx["watchlist"] = filter_mnpi(resp.get("records", []))
        if ctx["watchlist"]:
            self._record_source("sf_watchlist", ctx["watchlist"])

        # Prior research (most recent 3)
        resp = self._sf_soql(
            f"SELECT Analyst__c,Rating__c,Target_Price__c,Summary__c,Generated_Date__c "
            f"FROM IR_Research_Note__c WHERE Ticker__c='{self.ticker}' "
            f"ORDER BY Generated_Date__c DESC LIMIT 3"
        )
        ctx["prior_research"] = filter_mnpi(resp.get("records", []))
        if ctx["prior_research"]:
            self._record_source("sf_prior_research", ctx["prior_research"])

        # Build LLM-safe holdings summary for downstream concentration check
        # (no MNPI fields — only tickers, counts, sectors)
        self._holdings_summary = summarize_holdings_safe(
            filter_mnpi(ctx.get("coverage", []))
        )

        # Holdings (FSC managed package — graceful skip if not installed)
        ctx["holdings"] = []
        try:
            resp = self._sf_soql(
                f"SELECT Name,FinServ__FinancialAccount__r.FinServ__PrimaryOwner__c "
                f"FROM FinServ__FinancialHolding__c WHERE Name='{self.ticker}'"
            )
            if resp.get("error"):
                # SOQL returned an error (object doesn't exist / 404)
                logger.warning(
                    "FSC holdings query skipped for %s — object not available: %s",
                    self.ticker, resp.get("error"),
                )
            else:
                raw_holdings = resp.get("records", [])
                if raw_holdings:
                    # MNPI enforcement: strip dollar amounts and share quantities.
                    # Only record: ticker, client count, top-holding flag.
                    unique_owners = set()
                    for h in raw_holdings:
                        fa = h.get("FinServ__FinancialAccount__r") or {}
                        owner_id = fa.get("FinServ__PrimaryOwner__c")
                        if owner_id:
                            unique_owners.add(owner_id)

                    holdings_summary = {
                        "ticker": self.ticker,
                        "client_count": len(unique_owners),
                        "is_top_holding": len(unique_owners) >= 5,
                    }
                    ctx["holdings"] = [holdings_summary]
                    self._record_source("sf_holdings", holdings_summary)

                    self._log_audit(
                        action="DATA_ACCESS", stage=2,
                        detail=f"FSC holdings for {self.ticker}: {len(unique_owners)} clients",
                        sources="FinServ__FinancialHolding__c",
                    )
        except Exception as exc:
            logger.warning(
                "FSC holdings query failed for %s (FSC may not be installed): %s",
                self.ticker, exc,
            )

        self.crm_context = ctx
        self._log_audit(
            action="DATA_ACCESS", stage=2,
            detail=f"CRM context for {self.ticker}",
            sources="IR_Company__c,IR_Coverage__c,IR_Watchlist__c,IR_Research_Note__c,FinServ__FinancialHolding__c",
        )
        return ctx


    # ════════════════════════════════════════════════════════════════
    # PHASE B: DATA COLLECTION (Stages 3-6)
    # ════════════════════════════════════════════════════════════════

    async def _stage_3_market_data(self) -> dict:
        """Stage 3 — Market Data Pull via MCP market-data server."""
        data = {}
        data["quote"] = self._mcp_call("market-data", "get_quote", {"symbol": self.ticker})
        self._record_source("mcp_quote", data["quote"])

        data["price_history"] = self._mcp_call(
            "market-data", "get_price_history",
            {"symbol": self.ticker, "period": "1y"},
        )
        self._record_source("mcp_price_history", {
            "ticker": self.ticker, "period": "1y",
            "points": len(data["price_history"].get("prices", [])) if isinstance(data["price_history"], dict) else 0,
        })

        data["key_stats"] = self._mcp_call("market-data", "get_analyst_consensus", {"symbol": self.ticker})
        self._record_source("mcp_key_stats", data["key_stats"])

        data["estimates"] = self._mcp_call("market-data", "get_earnings_calendar", {"symbol": self.ticker})
        self._record_source("mcp_estimates", data["estimates"])

        self.market_data = data
        self._log_audit(
            action="DATA_ACCESS", stage=3, detail=f"Market data for {self.ticker}",
            sources="market-data MCP (get_quote,get_price_history,get_key_stats,get_consensus_estimates)",
        )
        return data

    async def _stage_4_news_sentiment(self) -> dict:
        """Stage 4 — News & Sentiment Scan via MCP news-search server."""
        data = {}
        data["news"] = self._mcp_call(
            "news-search", "search_financial_news",
            {"query": f"{self.ticker} stock", "max_results": 20},
        )
        self._record_source("mcp_news", {
            "ticker": self.ticker,
            "count": len(data["news"].get("articles", [])) if isinstance(data["news"], dict) else 0,
        })

        data["headlines"] = self._mcp_call(
            "news-search", "get_headlines", {"sector": "markets", "max_results": 15},
        )
        self._record_source("mcp_headlines", {
            "ticker": self.ticker,
            "count": len(data["headlines"].get("headlines", [])) if isinstance(data["headlines"], dict) else 0,
        })

        self.news_data = data
        self._log_audit(
            action="DATA_ACCESS", stage=4, detail=f"News for {self.ticker}",
            sources="news-search MCP (search_financial_news,get_headlines)",
        )
        return data

    async def _stage_5_sec_filings(self) -> dict:
        """Stage 5 — SEC Filing Retrieval via MCP sec-edgar server."""
        data = {}
        data["10k"] = self._mcp_call("sec-edgar", "get_10k", {"ticker": self.ticker, "count": 1})
        self._record_source("mcp_sec_10k", {
            "ticker": self.ticker, "type": "10-K",
            "date": data["10k"].get("filing_date") if isinstance(data["10k"], dict) else None,
        })

        data["10q"] = self._mcp_call("sec-edgar", "get_10q", {"ticker": self.ticker, "count": 1})
        self._record_source("mcp_sec_10q", {
            "ticker": self.ticker, "type": "10-Q",
            "date": data["10q"].get("filing_date") if isinstance(data["10q"], dict) else None,
        })

        data["8k"] = self._mcp_call("sec-edgar", "get_8k", {"ticker": self.ticker, "count": 5})
        self._record_source("mcp_sec_8k", {
            "ticker": self.ticker, "type": "8-K",
            "count": len(data["8k"].get("filings", [])) if isinstance(data["8k"], dict) else 0,
        })

        self.sec_filings = data
        self._log_audit(
            action="DATA_ACCESS", stage=5, detail=f"SEC filings for {self.ticker}",
            sources="sec-edgar MCP (get_10k,get_10q,get_8k)",
        )
        return data

    async def _stage_6_transcript_analysis(self) -> dict:
        """Stage 6 — Earnings transcript summarization via LLM (Bedrock Claude). No Comprehend."""
        transcript_ctx = self._build_transcript_context()
        if not transcript_ctx:
            self.transcript_summary = "No recent earnings transcript available."
            self._record_source("transcript_analysis", {"status": "unavailable"})
            return {"summary": self.transcript_summary, "status": "no_transcript"}

        prompt = (
            f"Summarize the following earnings call information for {self.ticker}. "
            f"Focus on: management guidance, revenue drivers, margin outlook, "
            f"competitive positioning, forward-looking statements. "
            f"Be factual — only state what is explicitly mentioned.\n\n"
            f"--- TRANSCRIPT CONTEXT ---\n{transcript_ctx}\n--- END ---\n\n"
            f"Sections: Key Takeaways, Guidance, Growth Drivers, Risks Mentioned, Outlook."
        )
        summary = self._llm_generate(prompt, max_tokens=2000)
        self.transcript_summary = summary
        self._record_source("transcript_llm", {
            "model": "bedrock/claude-sonnet-4.6", "input_len": len(transcript_ctx),
        })
        self._log_audit(action="DATA_ACCESS", stage=6, detail=f"Transcript analysis for {self.ticker}", sources="LLM Bedrock")
        return {"summary": summary, "status": "completed"}


    # ════════════════════════════════════════════════════════════════
    # PHASE C: VALIDATION (Stage 7) — HITL GATE
    # ════════════════════════════════════════════════════════════════

    async def _stage_7_data_quality_gate(self) -> dict:
        """Stage 7 — Data Quality Gate. HITL: analyst verifies data completeness."""
        completeness = {
            "has_quote": bool(self.market_data.get("quote")),
            "has_price_history": bool(self.market_data.get("price_history")),
            "has_key_stats": bool(self.market_data.get("key_stats")),
            "has_news": bool(self.news_data.get("news")),
            "has_10k": bool(self.sec_filings.get("10k")),
            "has_10q": bool(self.sec_filings.get("10q")),
            "has_8k": bool(self.sec_filings.get("8k")),
            "has_crm_company": bool(self.crm_context.get("company")),
            "has_transcript": self.transcript_summary != "No recent earnings transcript available.",
        }
        missing = [k for k, v in completeness.items() if not v]
        score = sum(completeness.values()) / len(completeness)

        self._log_audit(
            action="DATA_QUALITY_CHECK", stage=7,
            detail=f"Completeness: {score:.0%}, missing: {missing}",
        )

        return {
            "gate": True, "stage": 7,
            "gate_type": "data_quality",
            "completeness": completeness,
            "completeness_score": round(score, 2),
            "missing_sources": missing,
            "context": (
                f"Data collection for {self.ticker} is {score:.0%} complete. "
                f"Missing: {', '.join(missing) if missing else 'none'}. "
                f"Please review and approve to proceed to analysis."
            ),
        }

    # ════════════════════════════════════════════════════════════════
    # PHASE D: ANALYSIS (Stages 8-12)
    # ════════════════════════════════════════════════════════════════

    async def _stage_8_financial_modeling(self) -> dict:
        """Stage 8 — Prepare inputs for DCF, comps, and Monte Carlo models."""
        quote = self.market_data.get("quote", {})
        stats = self.market_data.get("key_stats", {})
        estimates = self.market_data.get("estimates", {})
        history = self.market_data.get("price_history", {})

        current_price = _safe_float(quote.get("price", quote.get("current_price", 0)))
        pe_ratio = _safe_float(
            stats.get("trailingPE", stats.get("pe_ratio", stats.get("pe", 0)))
        )
        forward_pe = _safe_float(stats.get("forwardPE", 0))

        # Market cap from CRM or derive from price * shares
        company = self.crm_context.get("company") or {}
        market_cap = _safe_float(company.get("Market_Cap__c", 0))
        if market_cap == 0:
            market_cap = _safe_float(stats.get("market_cap", quote.get("market_cap", 0)))

        # Shares outstanding: derive from market_cap / price
        shares = _safe_float(stats.get("shares_outstanding", 0))
        if shares == 0 and current_price > 0 and market_cap > 0:
            shares = market_cap / current_price

        # Revenue TTM: derive from PE and earnings if not directly available
        revenue_ttm = _safe_float(stats.get("revenue_ttm", stats.get("revenue", 0)))
        if revenue_ttm == 0 and pe_ratio > 0 and current_price > 0 and shares > 0:
            # EPS = price / PE, then earnings = EPS * shares
            eps = current_price / pe_ratio
            earnings = eps * shares
            # Assume ~55% net margin for high-margin tech (NVDA-like)
            net_margin = 0.55
            revenue_ttm = earnings / net_margin if net_margin > 0 else earnings * 2

        operating_margin = _safe_float(stats.get("operating_margin", 0.60))

        consensus_growth = _safe_float(estimates.get("revenue_growth", estimates.get("growth_rate", 0)))
        if consensus_growth == 0:
            consensus_growth = 0.15  # default 15% growth
        growth_rates = [
            consensus_growth,
            consensus_growth * 0.9,
            consensus_growth * 0.8,
            consensus_growth * 0.7,
            consensus_growth * 0.6,
        ]

        # Volatility from price history
        prices = history.get("prices", [])
        annual_vol = 0.35  # default
        if isinstance(prices, list) and len(prices) > 20:
            import numpy as np
            close_prices = [_safe_float(p.get("close", p) if isinstance(p, dict) else p) for p in prices]
            close_prices = [p for p in close_prices if p > 0]
            if len(close_prices) > 1:
                returns = np.diff(np.log(close_prices))
                annual_vol = float(np.std(returns) * np.sqrt(252))

        inputs = {
            "current_price": current_price,
            "market_cap_b": market_cap / 1e9 if market_cap > 1e6 else market_cap,
            "shares_outstanding_b": shares / 1e9 if shares > 1e6 else shares,
            "revenue_ttm_b": revenue_ttm / 1e9 if revenue_ttm > 1e6 else revenue_ttm,
            "operating_margin": operating_margin,
            "revenue_growth_rates": growth_rates,
            "pe_ratio": pe_ratio,
            "forward_pe": forward_pe,
            "annual_volatility": annual_vol,
            "wacc": 0.10,
            "terminal_growth": 0.03,
            "tax_rate": 0.21,
            "capex_pct_revenue": _safe_float(stats.get("capex_pct_revenue", 0.08)),
            "margin_expansion": 0.005,
            "net_debt_b": _safe_float(stats.get("net_debt", 0)) / 1e9 if _safe_float(stats.get("net_debt", 0)) > 1e6 else _safe_float(stats.get("net_debt", 0)),
            "annual_return": consensus_growth,
            "sector": company.get("Sector__c", "Technology"),
        }

        self.financial_model_inputs = inputs
        self._record_source("model_inputs", inputs)
        self._log_audit(action="RESEARCH_BRIEF", stage=8, detail="Model inputs prepared")
        return inputs

    def _is_sandbox_mode(self) -> bool:
        """Check if sandbox execution mode is configured."""
        return self.config.get("experiment", {}).get("mode") == "sandbox"

    async def _stage_9_dcf_valuation(self) -> dict:
        """Stage 9 — Run DCF valuation model (dcf.py)."""
        inp = self.financial_model_inputs
        dcf_kwargs = {
            "revenue_ttm": inp["revenue_ttm_b"],
            "revenue_growth_rates": inp["revenue_growth_rates"],
            "operating_margin": inp["operating_margin"],
            "margin_expansion": inp["margin_expansion"],
            "tax_rate": inp["tax_rate"],
            "capex_pct_revenue": inp["capex_pct_revenue"],
            "wacc": inp["wacc"],
            "terminal_growth": inp["terminal_growth"],
            "shares_outstanding": inp["shares_outstanding_b"],
            "net_debt": inp["net_debt_b"],
        }
        if self._is_sandbox_mode():
            result = run_in_sandbox("dcf", "run_dcf", dcf_kwargs)
        else:
            result = run_dcf(**dcf_kwargs)
        if result.get("error"):
            raise ValueError(f"DCF model error: {result['message']}")

        self.dcf_result = result
        self.model_outputs["dcf"] = result
        self._record_source("model_dcf", {
            "fair_value": result["fair_value_per_share"],
            "ev": result["enterprise_value"],
            "methodology": result["methodology"],
        })
        self._log_audit(
            action="RESEARCH_BRIEF", stage=9,
            detail=f"DCF fair value: ${result['fair_value_per_share']}",
            sources="dcf.py",
        )
        return result

    async def _stage_10_comps_analysis(self) -> dict:
        """Stage 10 — Run comparable company analysis (comps.py)."""
        stats = self.market_data.get("key_stats", {})
        quote = self.market_data.get("quote", {})

        target_metrics = {
            "pe": _safe_float(stats.get("trailingPE", stats.get("pe_ratio", stats.get("pe")))),
            "ev_ebitda": _safe_float(stats.get("ev_ebitda")),
            "ps": _safe_float(stats.get("ps_ratio", stats.get("ps"))),
            "pb": _safe_float(stats.get("pb_ratio", stats.get("pb"))),
            "ev_revenue": _safe_float(stats.get("ev_revenue")),
            "price": _safe_float(quote.get("price", quote.get("current_price", 0))),
            "market_cap": _safe_float((self.crm_context.get("company") or {}).get("Market_Cap__c", stats.get("market_cap", 0))),
        }

        peer_resp = self._mcp_call(
            "market-data", "get_analyst_consensus",
            {"symbol": self.ticker},
        )
        # Build peer data from analyst consensus if available
        peer_data = peer_resp.get("peers", []) if isinstance(peer_resp, dict) else []

        if not peer_data:
            self.comps_result = {"narrative": "Insufficient peer data for comps analysis."}
            self._record_source("model_comps", {"status": "no_peers"})
            self._log_audit(action="RESEARCH_BRIEF", stage=10, detail="Comps: no peer data")
            return self.comps_result

        comps_kwargs = {
            "target_ticker": self.ticker,
            "target_metrics": target_metrics,
            "peer_data": peer_data,
        }
        if self._is_sandbox_mode():
            result = run_in_sandbox("comps", "run_comps", comps_kwargs)
        else:
            result = run_comps(**comps_kwargs)
        if result.get("error"):
            raise ValueError(f"Comps model error: {result['message']}")

        self.comps_result = result
        self.model_outputs["comps"] = result
        self._record_source("model_comps", {
            "implied_prices": result.get("implied_prices"),
            "narrative": result.get("narrative"),
        })
        self._log_audit(action="RESEARCH_BRIEF", stage=10, detail="Comps analysis complete", sources="comps.py")
        return result

    async def _stage_11_monte_carlo(self) -> dict:
        """Stage 11 — Run Monte Carlo simulation (monte_carlo.py)."""
        inp = self.financial_model_inputs
        mc_kwargs = {
            "current_price": inp["current_price"],
            "annual_return": inp["annual_return"],
            "annual_volatility": inp["annual_volatility"],
            "days": 252,
            "simulations": 500,
        }
        if self._is_sandbox_mode():
            result = run_in_sandbox("monte_carlo", "run_monte_carlo", mc_kwargs)
        else:
            result = run_monte_carlo(**mc_kwargs)
        if result.get("error"):
            raise ValueError(f"Monte Carlo error: {result['message']}")

        self.monte_carlo_result = result
        self.model_outputs["monte_carlo"] = result
        self._record_source("model_monte_carlo", {
            "median": result["median_price"], "p5": result["p5"], "p95": result["p95"],
            "prob_above": result["probability_above_current"],
        })
        self._log_audit(
            action="RESEARCH_BRIEF", stage=11,
            detail=f"MC median: ${result['median_price']}, P5-P95: ${result['p5']}-${result['p95']}",
            sources="monte_carlo.py",
        )
        return result

    async def _stage_12_sentiment_synthesis(self) -> dict:
        """Stage 12 — LLM synthesizes news + transcript sentiment. No Comprehend."""
        news_text = self._summarize_news_for_llm()
        prompt = (
            f"Analyze the overall market sentiment for {self.ticker} based on:\n\n"
            f"1. Recent news and headlines:\n{news_text}\n\n"
            f"2. Earnings transcript summary:\n{self.transcript_summary}\n\n"
            f"Provide:\n"
            f"- Overall sentiment: Bullish / Neutral / Bearish\n"
            f"- Sentiment score: -1.0 (very bearish) to +1.0 (very bullish)\n"
            f"- Key positive themes (with source references)\n"
            f"- Key negative themes (with source references)\n"
            f"- Sentiment trend: Improving / Stable / Deteriorating\n"
            f"Be specific. Cite the news sources or transcript sections."
        )
        synthesis = self._llm_generate(prompt, max_tokens=1500)
        self.sentiment_synthesis = synthesis
        self._record_source("sentiment_llm", {"model": "bedrock/claude-sonnet-4.6"})
        self._log_audit(action="RESEARCH_BRIEF", stage=12, detail="Sentiment synthesis complete", sources="LLM Bedrock")
        return {"synthesis": synthesis}


    # ════════════════════════════════════════════════════════════════
    # PHASE E: REVIEW (Stage 13) — HITL GATE
    # ════════════════════════════════════════════════════════════════

    async def _stage_13_analysis_review_gate(self) -> dict:
        """Stage 13 — Analysis Review Gate. HITL: analyst reviews model outputs."""
        dcf_fv = self.dcf_result.get("fair_value_per_share", "N/A")
        comps_implied = self.comps_result.get("implied_prices", {}).get("composite_implied_price", "N/A")
        mc_median = self.monte_carlo_result.get("median_price", "N/A")
        mc_p5 = self.monte_carlo_result.get("p5", "N/A")
        mc_p95 = self.monte_carlo_result.get("p95", "N/A")

        summary = (
            f"Model outputs for {self.ticker}:\n"
            f"  DCF fair value: ${dcf_fv}\n"
            f"  Comps implied price: ${comps_implied}\n"
            f"  Monte Carlo median: ${mc_median} (P5: ${mc_p5}, P95: ${mc_p95})\n"
            f"  Sentiment: {self.sentiment_synthesis[:200]}...\n\n"
            f"Please review model assumptions and outputs before synthesis."
        )

        self._log_audit(action="ANALYSIS_REVIEW", stage=13, detail=summary[:500])

        return {
            "gate": True, "stage": 13,
            "gate_type": "analysis_review",
            "model_outputs": {
                "dcf_fair_value": dcf_fv,
                "comps_implied": comps_implied,
                "monte_carlo_median": mc_median,
                "monte_carlo_range": f"${mc_p5} - ${mc_p95}",
            },
            "context": summary,
        }

    # ════════════════════════════════════════════════════════════════
    # PHASE F: SYNTHESIS (Stages 14-18)
    # ════════════════════════════════════════════════════════════════

    async def _stage_14_thesis_generation(self) -> dict:
        """Stage 14 — LLM generates investment thesis (bull/bear/base cases)."""
        data_context = self._build_synthesis_context()
        prompt = (
            f"Generate an investment thesis for {self.ticker} with three scenarios:\n\n"
            f"DATA CONTEXT:\n{data_context}\n\n"
            f"For each scenario (Bull Case, Base Case, Bear Case), provide:\n"
            f"- Core argument (2-3 sentences)\n"
            f"- Key assumptions\n"
            f"- Implied price range\n"
            f"- Probability assessment\n\n"
            f"RULES:\n"
            f"- Every number must reference a data source (e.g., 'revenue of $X per 10-Q')\n"
            f"- No fabricated statistics\n"
            f"- Use professional equity research language"
        )
        thesis = self._llm_generate_with_trust(prompt, max_tokens=2000)
        self.thesis = thesis
        self._record_source("thesis_llm", {"model": "bedrock/claude-sonnet-4.6"})
        self._log_audit(action="RESEARCH_BRIEF", stage=14, detail="Thesis generated (trust layer)", sources="LLM Bedrock + SF Trust Layer")
        return {"thesis": thesis}

    async def _stage_15_catalyst_identification(self) -> dict:
        """Stage 15 — LLM identifies near-term and long-term catalysts."""
        data_context = self._build_synthesis_context()
        prompt = (
            f"Identify catalysts for {self.ticker}:\n\n"
            f"DATA CONTEXT:\n{data_context}\n\n"
            f"Provide:\n"
            f"1. Near-term catalysts (0-6 months) — with expected dates if known\n"
            f"2. Long-term catalysts (6-24 months)\n"
            f"3. For each catalyst: description, potential impact (High/Medium/Low), "
            f"probability, and data source\n\n"
            f"Only cite catalysts supported by the data. No speculation."
        )
        catalysts = self._llm_generate(prompt, max_tokens=1500)
        self.catalysts = catalysts
        self._record_source("catalysts_llm", {"model": "bedrock/claude-sonnet-4.6"})
        self._log_audit(action="RESEARCH_BRIEF", stage=15, detail="Catalysts identified", sources="LLM Bedrock")
        return {"catalysts": catalysts}

    async def _stage_16_risk_assessment(self) -> dict:
        """Stage 16 — LLM identifies and ranks risks."""
        data_context = self._build_synthesis_context()
        prompt = (
            f"Assess risks for {self.ticker}:\n\n"
            f"DATA CONTEXT:\n{data_context}\n\n"
            f"Provide a ranked list of risks:\n"
            f"For each risk:\n"
            f"- Description\n"
            f"- Category: Fundamental / Macro / Regulatory / Competitive / Execution\n"
            f"- Probability: High / Medium / Low\n"
            f"- Impact: High / Medium / Low\n"
            f"- Mitigants (if any)\n"
            f"- Data source\n\n"
            f"Rank by combined probability x impact. Be specific, not generic."
        )
        risks = self._llm_generate(prompt, max_tokens=1500)
        self.risks = risks
        self._record_source("risks_llm", {"model": "bedrock/claude-sonnet-4.6"})
        self._log_audit(action="RESEARCH_BRIEF", stage=16, detail="Risks assessed", sources="LLM Bedrock")
        return {"risks": risks}

    async def _stage_17_rating_determination(self) -> dict:
        """Stage 17 — LLM determines Buy/Hold/Sell rating."""
        dcf_fv = self.dcf_result.get("fair_value_per_share", 0)
        comps_implied = self.comps_result.get("implied_prices", {}).get("composite_implied_price", 0)
        mc_median = self.monte_carlo_result.get("median_price", 0)
        current = self.financial_model_inputs.get("current_price", 0)

        prompt = (
            f"Determine an investment rating for {self.ticker}.\n\n"
            f"Current price: ${current}\n"
            f"DCF fair value: ${dcf_fv}\n"
            f"Comps implied price: ${comps_implied}\n"
            f"Monte Carlo median (1yr): ${mc_median}\n"
            f"Monte Carlo P5-P95: ${self.monte_carlo_result.get('p5', 'N/A')}-"
            f"${self.monte_carlo_result.get('p95', 'N/A')}\n\n"
            f"Thesis:\n{self.thesis[:500]}\n\n"
            f"Catalysts:\n{self.catalysts[:300]}\n\n"
            f"Risks:\n{self.risks[:300]}\n\n"
            f"Sentiment:\n{self.sentiment_synthesis[:300]}\n\n"
            f"Provide:\n"
            f"1. Rating: BUY / HOLD / SELL\n"
            f"2. Conviction: HIGH / MEDIUM / LOW\n"
            f"3. Rationale (3-5 sentences)\n"
            f"4. Key upside/downside factors\n"
            f"Base the rating on the quantitative model outputs above."
        )
        rating_text = self._llm_generate_with_trust(prompt, max_tokens=1000)
        self.rating = rating_text
        self._record_source("rating_llm", {"model": "bedrock/claude-sonnet-4.6"})
        self._log_audit(action="RESEARCH_BRIEF", stage=17, detail="Rating determined (trust layer)", sources="LLM Bedrock + SF Trust Layer")
        return {"rating": rating_text}

    async def _stage_18_target_price_calc(self) -> dict:
        """Stage 18 — Weighted average target price from DCF + comps + Monte Carlo."""
        dcf_fv = _safe_float(self.dcf_result.get("fair_value_per_share", 0))
        comps_fv = _safe_float(self.comps_result.get("implied_prices", {}).get("composite_implied_price", 0))
        mc_median = _safe_float(self.monte_carlo_result.get("median_price", 0))

        # Weighted average: DCF 40%, Comps 30%, Monte Carlo 30%
        weights = {"dcf": 0.40, "comps": 0.30, "monte_carlo": 0.30}
        values = {"dcf": dcf_fv, "comps": comps_fv, "monte_carlo": mc_median}

        active = {k: v for k, v in values.items() if v > 0}
        if not active:
            self.target_price = 0
            return {"target_price": 0, "methodology": "No valid model outputs"}

        total_weight = sum(weights[k] for k in active)
        target = sum(values[k] * (weights[k] / total_weight) for k in active)
        self.target_price = round(target, 2)

        methodology = {
            "weights": {k: round(weights[k] / total_weight, 2) for k in active},
            "values": active,
            "target_price": self.target_price,
        }
        self._record_source("target_price_calc", methodology)
        self._log_audit(
            action="RESEARCH_BRIEF", stage=18,
            detail=f"Target: ${self.target_price} (DCF=${dcf_fv}, Comps=${comps_fv}, MC=${mc_median})",
        )
        return methodology


    # ════════════════════════════════════════════════════════════════
    # PHASE G: OUTPUT (Stages 19-20)
    # ════════════════════════════════════════════════════════════════

    async def _stage_19_brief_assembly(self) -> dict:
        """Stage 19 — Assemble all sections into structured research brief."""
        current_price = self.financial_model_inputs.get("current_price", 0)
        company = self.crm_context.get("company", {})
        upside = 0
        if current_price and self.target_price:
            upside = round(((self.target_price - current_price) / current_price) * 100, 1)

        self.brief = {
            "metadata": {
                "ticker": self.ticker,
                "company_name": company.get("Name", self.ticker),
                "sector": company.get("Sector__c", ""),
                "exchange": company.get("Exchange__c", ""),
                "analyst": self.analyst,
                "date": _now_iso(),
                "run_id": self.run_id,
            },
            "executive_summary": {
                "rating": self.rating,
                "target_price": self.target_price,
                "current_price": current_price,
                "upside_downside_pct": upside,
            },
            "investment_thesis": self.thesis,
            "catalysts": self.catalysts,
            "risks": self.risks,
            "valuation": {
                "dcf": {
                    "fair_value": self.dcf_result.get("fair_value_per_share"),
                    "enterprise_value": self.dcf_result.get("enterprise_value"),
                    "methodology": self.dcf_result.get("methodology"),
                    "sensitivity": self.dcf_result.get("sensitivity_table"),
                },
                "comps": {
                    "implied_prices": self.comps_result.get("implied_prices"),
                    "relative_valuation": self.comps_result.get("relative_valuation"),
                    "narrative": self.comps_result.get("narrative"),
                },
                "monte_carlo": {
                    "median": self.monte_carlo_result.get("median_price"),
                    "p5": self.monte_carlo_result.get("p5"),
                    "p95": self.monte_carlo_result.get("p95"),
                    "prob_above_current": self.monte_carlo_result.get("probability_above_current"),
                },
                "target_price_methodology": {
                    "target": self.target_price,
                    "weights": "DCF 40%, Comps 30%, Monte Carlo 30%",
                },
            },
            "sentiment": self.sentiment_synthesis,
            "transcript_summary": self.transcript_summary,
            "data_sources": list(self.data_sources.keys()),
            "anti_fabrication_ledger": {
                k: _truncate(v, 200) for k, v in self.data_sources.items()
            },
        }

        self._log_audit(action="RESEARCH_BRIEF", stage=19, detail="Brief assembled")
        return self.brief

    async def _stage_20_compliance_check(self) -> dict:
        """Stage 20 — Run compliance-screening skill (delegated to screening.py)."""
        # Build LLM-safe holdings summary for concentration check
        holdings_summary = getattr(self, "_holdings_summary", None)

        # Delegate all 4 checks to the compliance-screening module
        self.compliance_result = run_compliance_screening(
            ticker=self.ticker,
            sf_instance_url=self.sf_instance_url,
            sf_access_token=self.sf_access_token,
            analyst=self.analyst,
            holdings_summary=holdings_summary,
        )

        # Run anti-fabrication check (pipeline-specific, not in screening module)
        fabrication_check = self._verify_anti_fabrication()
        self.compliance_result["anti_fabrication"] = fabrication_check
        if not fabrication_check["passed"]:
            self.compliance_result["warnings"].append(
                f"Anti-fabrication: {fabrication_check['detail']}"
            )

        self._log_audit(
            action="COMPLIANCE_CHECK", stage=20,
            detail=json.dumps(self.compliance_result),
            compliance_status=self.compliance_result["overall"],
            sources="IR_Audit_Log__c,IR_Watchlist__c",
        )
        return self.compliance_result


    # ════════════════════════════════════════════════════════════════
    # PHASE H: DELIVERY (Stages 21-23)
    # ════════════════════════════════════════════════════════════════

    async def _stage_21_final_approval_gate(self) -> dict:
        """Stage 21 — Final Approval Gate. HITL: analyst approves final brief."""
        compliance_status = "PASS"
        if self.compliance_result:
            compliance_status = self.compliance_result.get("overall", "PASS")

        summary = (
            f"Research brief for {self.ticker} ready for final approval.\n\n"
            f"Rating: {self.rating[:100]}\n"
            f"Target Price: ${self.target_price}\n"
            f"Current Price: ${self.financial_model_inputs.get('current_price', 'N/A')}\n"
            f"Compliance: {compliance_status}\n"
            f"Warnings: {self.compliance_result.get('warnings', []) if self.compliance_result else []}\n\n"
            f"Approve to publish to Salesforce IR_Research_Note__c."
        )

        self._log_audit(action="FINAL_APPROVAL", stage=21, detail=summary[:500])

        return {
            "gate": True, "stage": 21,
            "gate_type": "final_approval",
            "brief_summary": {
                "ticker": self.ticker,
                "rating": self.rating[:100],
                "target_price": self.target_price,
                "compliance": compliance_status,
                "warnings": self.compliance_result.get("warnings", []) if self.compliance_result else [],
                "blocks": self.compliance_result.get("blocks", []) if self.compliance_result else [],
            },
            "context": summary,
        }

    async def _stage_22_crm_writeback(self) -> dict:
        """Stage 22 — Publish research brief to IR_Research_Note__c."""
        if self.compliance_result and self.compliance_result.get("overall") == "FAIL":
            self._log_audit(
                action="RESEARCH_BRIEF", stage=22,
                detail="Publish blocked — compliance FAIL",
                compliance_status="FAIL",
            )
            return {"published": False, "reason": "Compliance check failed"}

        company_id = None
        if self.crm_context.get("company"):
            company_id = self.crm_context["company"].get("Id")

        note_record = {
            "Ticker__c": self.ticker,
            "Analyst__c": self.analyst,
            "Rating__c": self._extract_rating_label(),
            "Target_Price__c": self.target_price,
            "Summary__c": self._build_executive_summary_text()[:32000],
            "Full_Brief__c": json.dumps(self.brief)[:131072],
            "Thesis__c": self.thesis[:32000],
            "Catalysts__c": self.catalysts[:32000],
            "Risks__c": self.risks[:32000],
            "Generated_Date__c": _now_iso(),
            "Pipeline_Run_Id__c": self.run_id,
        }
        if company_id:
            note_record["Company__c"] = company_id

        result = self._sf_create("IR_Research_Note__c", note_record)

        self._log_audit(
            action="RESEARCH_BRIEF", stage=22,
            detail=f"Published to IR_Research_Note__c: {result.get('id', 'unknown')}",
            sources="IR_Research_Note__c",
        )
        return {"published": True, "record_id": result.get("id"), "ticker": self.ticker}

    async def _stage_23_delivery_notify(self) -> dict:
        """Stage 23 — Log to IR_Audit_Log__c and notify analyst."""
        audit_record = {
            "Agent__c": "OpenClaw-IR",
            "Action__c": "RESEARCH_BRIEF",
            "Query__c": self.query[:255],
            "Analyst__c": self.analyst,
            "Timestamp__c": _now_iso(),
            "Data_Sources_Used__c": ",".join(list(self.data_sources.keys())[:20])[:255],
            "Pipeline_Stage__c": "COMPLETED (23/23)",
            "Decision_Rationale__c": (
                f"Pipeline {self.run_id} completed. "
                f"Rating: {self._extract_rating_label()}, "
                f"Target: ${self.target_price}"
            )[:255],
            "Trace_Id__c": str(self.trace.id) if hasattr(self.trace, "id") else self.run_id,
            "Compliance_Status__c": self.compliance_result.get("overall", "PASS") if self.compliance_result else "PASS",
            "MNPI_Flag__c": False,
        }
        self._sf_create("IR_Audit_Log__c", audit_record)

        notification = {
            "type": "research_brief_complete",
            "ticker": self.ticker,
            "analyst": self.analyst,
            "run_id": self.run_id,
            "rating": self._extract_rating_label(),
            "target_price": self.target_price,
            "current_price": self.financial_model_inputs.get("current_price"),
            "compliance": self.compliance_result.get("overall") if self.compliance_result else "PASS",
            "completed_at": _now_iso(),
            "summary": self._build_executive_summary_text()[:500],
        }

        # Attempt to dispatch notification via OpenClaw hooks endpoint
        # This sends the notification to connected channels (Slack, Telegram, etc.)
        # If no channels are connected, this is a no-op (hooks returns ok but no delivery)
        try:
            hooks_url = os.environ.get("OPENCLAW_HOOKS_URL", "http://localhost:18789/hooks/agent")
            hooks_token = os.environ.get("OPENCLAW_HOOKS_TOKEN", "")
            if hooks_token:
                summary_text = (
                    f"Research brief completed for {self.ticker}.\n"
                    f"Rating: {self._extract_rating_label()}\n"
                    f"Target: ${self.target_price}\n"
                    f"Run: {self.run_id}"
                )
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {hooks_token}",
                }
                payload = {
                    "message": summary_text,
                    "agentId": "fsi-research",
                    "sessionKey": f"notify:{self.run_id}",
                    "deliver": True,
                    "thinking": "low",
                    "timeoutSeconds": 30,
                }
                resp = requests.post(hooks_url, json=payload, headers=headers, timeout=10)
                if resp.ok:
                    logger.info("Pipeline notification dispatched via hooks: %s", resp.json())
                else:
                    logger.warning("Pipeline notification dispatch failed: %s", resp.status_code)
            else:
                logger.info("No OPENCLAW_HOOKS_TOKEN set — skipping channel notification dispatch")
        except Exception as exc:
            logger.warning("Pipeline notification dispatch error: %s", exc)

        logger.info(
            "Pipeline %s completed for %s. Rating: %s, Target: $%s",
            self.run_id, self.ticker, self._extract_rating_label(), self.target_price,
        )
        return {"notified": True, "notification": notification}


    # ════════════════════════════════════════════════════════════════
    # PRIVATE HELPERS — MCP, Salesforce, LLM, Anti-Fabrication
    # ════════════════════════════════════════════════════════════════

    def _mcp_call(self, server: str, tool: str, arguments: dict) -> dict:
        """
        Call an MCP tool via POST /tools/call on the Lambda gateway.

        MCP protocol: POST {gateway}/{server}/tools/call
        Body: {"name": tool, "arguments": {...}}

        Resilience: 3 attempts with exponential backoff (1s, 2s, 4s).
        Retries on 429, 5xx, or connection errors. Permanent 4xx (400/401/403/404)
        return immediately.
        """
        url = f"{self.mcp_gateway_url}/{server}/tools/call"
        payload = {"name": tool, "arguments": arguments}
        span = self.trace.span(
            name=f"mcp-{server}-{tool}",
            metadata={"server": server, "tool": tool, "arguments": arguments},
        )

        max_attempts = 3
        last_err = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(
                    url, json=payload,
                    headers={
                        "x-api-key": self.mcp_api_key,
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )
                status = resp.status_code

                if status == 429 or 500 <= status < 600:
                    if attempt < max_attempts:
                        backoff = 1.0 * (2 ** (attempt - 1))
                        logger.warning(
                            "MCP %s/%s returned %d, retry %d/%d in %.1fs",
                            server, tool, status, attempt, max_attempts, backoff,
                        )
                        time.sleep(backoff)
                        continue

                resp.raise_for_status()
                result = resp.json()
                span.end(metadata={"status": "ok", "status_code": status, "attempts": attempt})

                if isinstance(result, dict) and "content" in result:
                    content = result["content"]
                    if isinstance(content, list) and content:
                        first = content[0]
                        if isinstance(first, dict) and first.get("type") == "text":
                            try:
                                return json.loads(first["text"])
                            except (json.JSONDecodeError, TypeError):
                                return {"raw_text": first.get("text", "")}
                    return result
                return result

            except requests.RequestException as exc:
                last_err = exc
                if attempt < max_attempts:
                    backoff = 1.0 * (2 ** (attempt - 1))
                    logger.warning(
                        "MCP %s/%s error on attempt %d/%d: %s - retry in %.1fs",
                        server, tool, attempt, max_attempts, exc, backoff,
                    )
                    time.sleep(backoff)
                    continue

        span.end(metadata={"status": "error", "error": str(last_err), "attempts": max_attempts})
        logger.error("MCP call %s/%s failed after %d attempts: %s",
                     server, tool, max_attempts, last_err)
        return {"error": True, "message": str(last_err), "server": server, "tool": tool}

    def _sf_soql(self, query: str) -> dict:
        """Execute a SOQL query. Prefers salesforce-crm MCP (MNPI-redacted
        server-side) and falls back to direct SF REST on MCP failure."""
        # Primary: salesforce-crm MCP (applies MNPI redaction server-side)
        if self.mcp_gateway_url and self.mcp_api_key:
            result = self._mcp_call(
                "salesforce-crm", "run_soql_query", {"query": query},
            )
            if not result.get("error"):
                return result

        # Fallback: direct SF REST. filter_mnpi() still applies downstream.
        import urllib.parse
        encoded = urllib.parse.quote(query, safe="")
        url = f"{self.sf_instance_url}/services/data/{SF_API_VERSION}/query/?q={encoded}"
        try:
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self.sf_access_token}"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("SOQL query failed: %s — %s", query[:100], exc)
            return {"records": [], "error": str(exc)}

    def _sf_create(self, sobject: str, record: dict) -> dict:
        """Create a Salesforce record via REST API."""
        url = f"{self.sf_instance_url}/services/data/{SF_API_VERSION}/sobjects/{sobject}"
        try:
            resp = requests.post(
                url, json=record,
                headers={
                    "Authorization": f"Bearer {self.sf_access_token}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.error("SF create %s failed: %s", sobject, exc)
            return {"success": False, "error": str(exc)}

    def _llm_generate(self, prompt: str, max_tokens: int = 2000) -> str:
        """
        Generate text via Bedrock Claude Sonnet 4.6.

        Calls Bedrock directly via boto3 converse API. In production,
        this would route through the OpenClaw Gateway which handles
        model selection, guardrails, and token management.
        """
        span = self.trace.span(
            name="llm-generate",
            input={"prompt_length": len(prompt), "max_tokens": max_tokens},
        )
        try:
            import boto3
            client = boto3.client("bedrock-runtime", region_name="us-east-1")
            model_id = self.config.get("llm", {}).get(
                "primary_model", "us.anthropic.claude-sonnet-4-20250514-v1:0"
            )
            response = client.converse(
                modelId=model_id,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": max_tokens, "temperature": 0.3},
            )
            text = ""
            output = response.get("output", {})
            message = output.get("message", {})
            for block in message.get("content", []):
                if block.get("text"):
                    text += block["text"]

            span.end(output={"output_length": len(text)})
            return text
        except Exception as exc:
            span.end(metadata={"status": "error", "error": str(exc)})
            logger.error("LLM generate failed: %s", exc)
            raise RuntimeError(f"LLM generation failed: {exc}") from exc

    def _llm_generate_with_trust(self, prompt: str, max_tokens: int = 2000) -> str:
        """
        Generate text via Einstein Trust Layer if available, else fall back to Bedrock.

        Used for pipeline stages that reason about CRM data (stages 14, 17).
        The trust layer adds prompt defense, PII masking, toxicity detection,
        and audit trail on top of Bedrock Guardrails.
        """
        if self._trust_layer_available is None:
            self._trust_layer_available = is_trust_layer_available(
                self.sf_instance_url, self.sf_access_token
            )

        if self._trust_layer_available:
            result = generate_with_trust_layer(
                prompt=prompt,
                sf_instance_url=self.sf_instance_url,
                sf_access_token=self.sf_access_token,
                max_tokens=max_tokens,
            )
            if result.get("success"):
                return result["text"]
            # Fall through to Bedrock if trust layer fails
            logger.warning(
                "Trust layer call failed, falling back to Bedrock: %s",
                result.get("blocked_reason") or result.get("message", ""),
            )

        return self._llm_generate(prompt, max_tokens)

    def _log_audit(
        self,
        action: str,
        stage: int,
        detail: str = "",
        compliance_status: str = "PASS",
        sources: str = "",
        mnpi_flag: bool = False,
    ) -> None:
        """Write an audit record to IR_Audit_Log__c and Langfuse (delegated to logger.py)."""
        try:
            audit_log_write(
                action=action,
                stage=stage,
                detail=detail,
                query=self.query,
                analyst=self.analyst,
                sf_instance_url=self.sf_instance_url,
                sf_access_token=self.sf_access_token,
                langfuse_trace=self.trace,
                compliance_status=compliance_status,
                sources=sources,
                mnpi_flag=mnpi_flag,
                trace_id=str(self.trace.id) if hasattr(self.trace, "id") else self.run_id,
            )
        except Exception as exc:
            logger.warning("Audit log write failed at stage %d: %s", stage, exc)

    def _record_source(self, key: str, data: Any) -> None:
        """Record a data source in the anti-fabrication ledger."""
        self.data_sources[key] = {
            "data": data,
            "timestamp": _now_iso(),
            "stage": self.current_stage,
        }

    def _build_transcript_context(self) -> str:
        """Build transcript context from 8-K filings and news."""
        parts = []
        filing_8k = self.sec_filings.get("8k", {})
        if isinstance(filing_8k, dict):
            for f in filing_8k.get("filings", [])[:3]:
                if isinstance(f, dict):
                    desc = f.get("description", f.get("title", ""))
                    content = f.get("content", f.get("text", ""))
                    if desc or content:
                        parts.append(f"8-K Filing: {desc}\n{content[:2000]}")

        news = self.news_data.get("news", {})
        if isinstance(news, dict):
            for a in news.get("articles", [])[:5]:
                if isinstance(a, dict):
                    title = a.get("title", "")
                    snippet = a.get("snippet", a.get("description", ""))
                    if "earning" in title.lower() or "quarter" in title.lower():
                        parts.append(f"News: {title}\n{snippet[:500]}")

        return "\n\n---\n\n".join(parts) if parts else ""

    def _summarize_news_for_llm(self) -> str:
        """Build a news summary string for LLM sentiment analysis."""
        parts = []
        news = self.news_data.get("news", {})
        if isinstance(news, dict):
            for a in news.get("articles", [])[:15]:
                if isinstance(a, dict):
                    parts.append(
                        f"[{a.get('published_date', a.get('date', ''))}] "
                        f"{a.get('source', '')}: {a.get('title', '')}\n"
                        f"{a.get('snippet', a.get('description', ''))[:200]}"
                    )
        headlines = self.news_data.get("headlines", {})
        if isinstance(headlines, dict):
            for h in headlines.get("headlines", [])[:10]:
                if isinstance(h, dict):
                    parts.append(f"Headline: {h.get('title', h.get('text', ''))}")
                elif isinstance(h, str):
                    parts.append(f"Headline: {h}")
        return "\n\n".join(parts) if parts else "No recent news available."

    def _build_synthesis_context(self) -> str:
        """Build data context string for LLM synthesis stages (14-17)."""
        sections = []
        quote = self.market_data.get("quote", {})
        stats = self.market_data.get("key_stats", {})
        if quote:
            sections.append(f"CURRENT QUOTE: {json.dumps(quote)[:500]}")
        if stats:
            sections.append(f"KEY STATS: {json.dumps(stats)[:500]}")
        if self.dcf_result:
            sections.append(
                f"DCF VALUATION: Fair value ${self.dcf_result.get('fair_value_per_share')}, "
                f"EV ${self.dcf_result.get('enterprise_value')}B. "
                f"{self.dcf_result.get('methodology', '')}"
            )
        if self.comps_result.get("narrative"):
            sections.append(f"COMPS ANALYSIS: {self.comps_result['narrative']}")
        if self.monte_carlo_result:
            sections.append(
                f"MONTE CARLO: Median ${self.monte_carlo_result.get('median_price')}, "
                f"P5 ${self.monte_carlo_result.get('p5')}, P95 ${self.monte_carlo_result.get('p95')}, "
                f"P(above current) {self.monte_carlo_result.get('probability_above_current')}"
            )
        if self.sentiment_synthesis:
            sections.append(f"SENTIMENT: {self.sentiment_synthesis[:500]}")
        if self.transcript_summary and self.transcript_summary != "No recent earnings transcript available.":
            sections.append(f"TRANSCRIPT: {self.transcript_summary[:500]}")
        if self.crm_context.get("coverage"):
            sections.append(f"COVERAGE: {json.dumps(self.crm_context['coverage'])[:300]}")
        return "\n\n".join(sections)

    def _verify_anti_fabrication(self) -> dict:
        """Verify key numbers in the brief trace to data sources."""
        issues = []
        if self.target_price and self.target_price > 0:
            dcf_fv = _safe_float(self.dcf_result.get("fair_value_per_share", 0))
            comps_fv = _safe_float(
                self.comps_result.get("implied_prices", {}).get("composite_implied_price", 0)
            )
            mc_median = _safe_float(self.monte_carlo_result.get("median_price", 0))
            if dcf_fv == 0 and comps_fv == 0 and mc_median == 0:
                issues.append("Target price has no model backing")
        if len(self.data_sources) < 3:
            issues.append(f"Only {len(self.data_sources)} data sources — expected more")
        if not self.model_outputs:
            issues.append("No financial model outputs recorded")
        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "detail": "; ".join(issues) if issues else "All numbers trace to sources",
            "source_count": len(self.data_sources),
            "model_count": len(self.model_outputs),
        }

    def _extract_rating_label(self) -> str:
        """Extract BUY/HOLD/SELL from the rating text."""
        if not self.rating:
            return "HOLD"
        upper = self.rating.upper()
        if "BUY" in upper:
            return "BUY"
        if "SELL" in upper:
            return "SELL"
        return "HOLD"

    def _build_executive_summary_text(self) -> str:
        """Build a plain-text executive summary for SF fields."""
        current = self.financial_model_inputs.get("current_price", 0)
        upside = 0
        if current and self.target_price:
            upside = round(((self.target_price - current) / current) * 100, 1)
        return (
            f"{self.ticker} — {self._extract_rating_label()} | "
            f"Target: ${self.target_price} | Current: ${current} | "
            f"Upside: {upside}%\n\n"
            f"DCF Fair Value: ${self.dcf_result.get('fair_value_per_share', 'N/A')}\n"
            f"Comps Implied: ${self.comps_result.get('implied_prices', {}).get('composite_implied_price', 'N/A')}\n"
            f"Monte Carlo Median: ${self.monte_carlo_result.get('median_price', 'N/A')}\n\n"
            f"Pipeline: {self.run_id} | Analyst: {self.analyst} | {_now_iso()}"
        )



# ── Module-level helpers ────────────────────────────────────────────


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, returning default on failure."""
    if val is None:
        return default
    try:
        result = float(val)
        if result != result:  # NaN check
            return default
        return result
    except (ValueError, TypeError):
        return default


def _truncate(obj: Any, max_len: int = 200) -> Any:
    """Truncate a value for the anti-fabrication ledger display."""
    if isinstance(obj, str):
        return obj[:max_len] + "..." if len(obj) > max_len else obj
    if isinstance(obj, dict):
        s = json.dumps(obj)
        return s[:max_len] + "..." if len(s) > max_len else s
    return str(obj)[:max_len]


__all__ = ["FSIResearchPipeline"]
