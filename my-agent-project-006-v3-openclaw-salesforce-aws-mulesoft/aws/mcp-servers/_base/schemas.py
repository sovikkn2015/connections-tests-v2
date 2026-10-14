"""Pydantic v2 models for the MCP wire protocol.

Every MCP tool call / response is modeled here so handlers never see
raw dicts except at the Lambda entry boundary.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    """A tool's contract — name, human description, JSON Schema for input."""

    name: str = Field(..., description="Tool name, snake_case")
    description: str
    input_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "required": []}
    )


class ToolCall(BaseModel):
    """Inbound tool invocation."""

    tool_call_id: str = Field(
        default="",
        description=(
            "Caller-supplied correlation id. Echoed into ToolResult so "
            "parallel tool calls can be matched on the client side."
        ),
    )
    name: str = Field(..., description="Tool name to invoke")
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolError(BaseModel):
    """Structured error body returned inside a ToolResult."""

    code: int
    message: str
    details: dict[str, Any] | None = None


class ToolResult(BaseModel):
    """Every tool call returns exactly one of these.

    Either `result` is set (success) or `error` is set (failure). Never both.
    """

    tool_call_id: str = ""
    status: Literal["ok", "error"] = "ok"
    result: dict[str, Any] | list[Any] | str | None = None
    error: ToolError | None = None
