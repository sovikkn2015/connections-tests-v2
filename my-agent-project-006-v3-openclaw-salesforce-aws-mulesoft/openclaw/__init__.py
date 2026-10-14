"""OpenClaw V3 — multi-agent FSI wealth platform.

17 agents across 3 personas (fsi-research, fsi-advisor, fsi-client-liaison)
on a single AgentCore runtime. Orchestrator-workers topology with
asyncio.gather fanout on the read path; serial writes through the trust spine.
"""

__version__ = "3.0.0"
