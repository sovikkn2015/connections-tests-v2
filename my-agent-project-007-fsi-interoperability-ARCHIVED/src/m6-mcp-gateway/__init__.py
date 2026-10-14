"""
M6 Trust-Aware MCP Gateway — THE CORE OF 007.

Every MCP call in the platform passes through this gateway. No exceptions.

Pre-call pipeline:  M1 (identity) → M2 (authority) → M4 (MNPI filter request)
Post-call pipeline: M4 (MNPI filter response) → Leakage Scan → M10 (audit)

Fail-closed on ANY trust check failure. No degraded mode.

Tech stack: FastAPI + httpx + circuitbreaker + tenacity + Redis
"""

__version__ = "0.1.0"
__module__ = "m6-mcp-gateway"
