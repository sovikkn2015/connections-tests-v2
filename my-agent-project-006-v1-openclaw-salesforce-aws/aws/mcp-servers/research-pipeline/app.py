"""
Research Pipeline MCP Server — bridges OpenClaw agent to the 23-stage pipeline.

The agent calls run_research_pipeline via MCP protocol. This server
instantiates FSIResearchPipeline and runs it. Pipeline pauses at HITL
gates (7, 13, 21) and returns gate context for analyst approval.

MCP Protocol: GET / + POST /tools/list + POST /tools/call
No credentials in code — all from environment variables.
Audit logging handled inside the pipeline (IR_Audit_Log__c + Langfuse).
"""

import asyncio
import json
import logging
import os
import sys

import yaml

# Add skills directories so pipeline.py can import its dependencies
SKILLS_DIR = os.environ.get("SKILLS_DIR", os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "openclaw", "skills"))
for sub in ("fsi-research", "financial-analysis", "compliance-screening",
            "audit-logging", "salesforce-crm"):
    sys.path.insert(0, os.path.join(SKILLS_DIR, sub))

# Shared MCP protocol handler
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from mcp_protocol import McpServer  # noqa: E402

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# In-memory run storage (persists across warm Lambda invocations)
_active_runs: dict = {}


def _load_config() -> dict:
    """Load AutoResearchClaw config."""
    p = os.environ.get("ARC_CONFIG_PATH", "")
    if p and os.path.exists(p):
        with open(p) as f:
            return yaml.safe_load(f)
    return {
        "llm": {"primary_model": "us.anthropic.claude-sonnet-4-20250514-v1:0"},
        "experiment": {"mode": "direct",
                       "repair": {"enabled": True, "max_cycles": 3}},
        "hitl": {"enabled": True},
    }


def _run_sync(ticker: str, query: str, analyst: str) -> dict:
    from pipeline import FSIResearchPipeline  # noqa: E402
    pipe = FSIResearchPipeline(ticker=ticker, query=query,
                               analyst=analyst, config=_load_config())
    _active_runs[pipe.run_id] = pipe
    return asyncio.run(pipe.run())


def _resume_sync(run_id: str, stage: int, approved: bool,
                 notes: str, analyst: str) -> dict:
    pipe = _active_runs.get(run_id)
    if not pipe:
        return {"error": True,
                "message": f"Run {run_id} not found (Lambda may have restarted)"}
    result = asyncio.run(pipe.resume(stage, {
        "approved": approved, "notes": notes, "analyst": analyst}))
    if result.get("status") in ("completed", "failed", "rejected"):
        _active_runs.pop(run_id, None)
    return result


def handle_run(params: dict) -> dict:
    ticker = params.get("ticker", "").upper().strip()
    query = params.get("query", "")
    analyst = params.get("analyst", "Analyst")
    if not ticker:
        return {"error": True, "message": "ticker is required"}
    if not query:
        return {"error": True, "message": "query is required"}
    logger.info("Pipeline start: %s — %s", ticker, query[:80])
    try:
        return _run_sync(ticker, query, analyst)
    except Exception as exc:
        logger.exception("Pipeline failed")
        return {"error": True, "message": str(exc)}


def handle_resume(params: dict) -> dict:
    run_id = params.get("run_id", "")
    stage = params.get("from_stage", 0)
    approved = params.get("approved", True)
    notes = params.get("notes", "")
    analyst = params.get("analyst", "Analyst")
    if not run_id or not stage:
        return {"error": True, "message": "run_id and from_stage required"}
    try:
        return _resume_sync(run_id, stage, approved, notes, analyst)
    except Exception as exc:
        logger.exception("Resume failed")
        return {"error": True, "message": str(exc)}


def handle_status(params: dict) -> dict:
    run_id = params.get("run_id", "")
    if not run_id:
        return {"error": True, "message": "run_id required"}
    pipe = _active_runs.get(run_id)
    if not pipe:
        return {"status": "not_found", "message": f"Run {run_id} not found"}
    return {"run_id": run_id, "ticker": pipe.ticker,
            "current_stage": pipe.current_stage,
            "completed_stages": pipe.completed_stages,
            "errors": pipe.errors}


server = McpServer(
    name="research-pipeline",
    version="1.0.0",
    description="23-stage FSI equity research pipeline",
)

server.register_tool("run_research_pipeline", {
    "description": (
        "Run the full 23-stage equity research pipeline. Produces a "
        "compliance-screened research brief with rating, target price, "
        "DCF, comps, Monte Carlo. Publishes to IR_Research_Note__c. "
        "Use for: deep dive, research brief, initiate coverage, "
        "earnings preview."
    ),
    "properties": {
        "ticker": {"type": "string",
                   "description": "Stock ticker (e.g. NVDA)"},
        "query": {"type": "string",
                  "description": "Full research query from analyst"},
        "analyst": {"type": "string",
                    "description": "Analyst name for audit trail"},
    },
    "required": ["ticker", "query"],
}, handle_run)

server.register_tool("resume_pipeline", {
    "description": (
        "Resume a paused pipeline after HITL gate approval. "
        "Gates at stages 7, 13, 21."
    ),
    "properties": {
        "run_id": {"type": "string", "description": "Pipeline run ID"},
        "from_stage": {"type": "integer",
                       "description": "Stage to resume from"},
        "approved": {"type": "boolean", "description": "Approved?"},
        "notes": {"type": "string", "description": "Analyst notes"},
        "analyst": {"type": "string", "description": "Analyst name"},
    },
    "required": ["run_id", "from_stage"],
}, handle_resume)

server.register_tool("get_pipeline_status", {
    "description": "Check status of a pipeline run.",
    "properties": {
        "run_id": {"type": "string", "description": "Pipeline run ID"},
    },
    "required": ["run_id"],
}, handle_status)


def lambda_handler(event, context):
    """AWS Lambda entry point."""
    return server.handle(event)
