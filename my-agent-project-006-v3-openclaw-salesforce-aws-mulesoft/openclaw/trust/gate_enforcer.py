"""Fail-closed enforcement of skill allowlist + MCP allowlist per agent.

Called before any tool invocation. A GateViolation here is treated as a
SAFETY-grade agent error by the coordinator (fail-closed, audit row,
no retry).

The allowlists come from the agent registry in orchestration/topology.py.
This module is the runtime boundary that makes those allowlists enforced,
not merely advisory.
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..orchestration.topology import AGENT_TOPOLOGY, AgentDefinition


class GateViolation(Exception):
    """Raised when an agent tries a tool/MCP call outside its allowlist.

    Callers MUST treat this as fail-closed: reject the call, write an audit
    row (IR_Audit_Log__c with Action__c = GATE_VIOLATION), abort the agent
    turn. No override flag.
    """

    def __init__(
        self,
        *,
        agent_id: str,
        kind: str,
        name: str,
        reason: str,
    ) -> None:
        self.agent_id = agent_id
        self.kind = kind
        self.name = name
        self.reason = reason
        super().__init__(
            f"gate_violation agent={agent_id} kind={kind} name={name} reason={reason}"
        )


class GateEnforcer:
    """Per-agent allowlist enforcement. Instances are cheap; reuse freely."""

    def __init__(self, registry: Optional[dict] = None) -> None:
        """
        Args:
            registry: optional override of AGENT_TOPOLOGY for tests.
        """
        self._registry = registry if registry is not None else AGENT_TOPOLOGY

    def check_tool(self, agent_id: str, tool_name: str) -> None:
        """Raise GateViolation if `tool_name` is not in agent's tool_allowlist."""
        agent = self._lookup(agent_id)
        if tool_name not in agent.tool_allowlist:
            raise GateViolation(
                agent_id=agent_id,
                kind="tool",
                name=tool_name,
                reason=(
                    f"tool {tool_name!r} not in allowlist "
                    f"{sorted(agent.tool_allowlist)!r}"
                ),
            )

    def check_mcp(self, agent_id: str, mcp_server: str) -> None:
        """Raise GateViolation if `mcp_server` is not in agent's mcp_allowlist."""
        agent = self._lookup(agent_id)
        if mcp_server not in agent.mcp_allowlist:
            raise GateViolation(
                agent_id=agent_id,
                kind="mcp",
                name=mcp_server,
                reason=(
                    f"mcp server {mcp_server!r} not in allowlist "
                    f"{sorted(agent.mcp_allowlist)!r}"
                ),
            )

    def check_write_safe(self, agent_id: str) -> None:
        """Raise GateViolation if agent has READ_ONLY memory scope.

        Second belt over the tool allowlist (which is the suspenders): the
        faq_specialist and liaison's context_specialist must never reach any
        write path.
        """
        agent = self._lookup(agent_id)
        from ..orchestration.topology import MemoryScope

        if any(scope is MemoryScope.READ_ONLY for scope in agent.memory_scope):
            raise GateViolation(
                agent_id=agent_id,
                kind="write",
                name="*",
                reason="agent has READ_ONLY memory scope; writes are forbidden",
            )

    def batch_check(
        self,
        agent_id: str,
        *,
        tools: Iterable[str] = (),
        mcps: Iterable[str] = (),
    ) -> None:
        """Convenience: run check_tool + check_mcp for multiple names."""
        for t in tools:
            self.check_tool(agent_id, t)
        for m in mcps:
            self.check_mcp(agent_id, m)

    def _lookup(self, agent_id: str) -> AgentDefinition:
        agent = self._registry.get(agent_id)
        if agent is None:
            raise GateViolation(
                agent_id=agent_id,
                kind="registry",
                name="*",
                reason=f"unknown agent id {agent_id!r}",
            )
        return agent
