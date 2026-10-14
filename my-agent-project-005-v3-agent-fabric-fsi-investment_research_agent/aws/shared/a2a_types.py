"""
Shared A2A (Agent2Agent) protocol types — minimal models pinned to
Google A2A spec v0.1.0 (2025).

Spec: https://github.com/a2aproject/A2A

Only the fields we actually use are modeled. Types are intentionally
loose (Any/dict) in places the spec allows arbitrary content (e.g. Part
data payloads) so vendor-specific A2A clients stay interoperable.

The runtime (AWS Lambda, python3.10) has pydantic v1 available through
boto3's dependency tree, but to stay zero-dependency we fall back to
plain dataclasses if pydantic cannot be imported.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

try:  # pragma: no cover
    from pydantic import BaseModel, Field
    _HAS_PYDANTIC = True
except ImportError:  # pragma: no cover
    from dataclasses import dataclass, field

    def Field(default=None, **_kwargs):  # type: ignore[no-redef]
        return default

    class BaseModel:  # minimal stand-in
        def __init__(self, **data):
            for k, v in data.items():
                setattr(self, k, v)

        def model_dump(self, exclude_none: bool = False) -> Dict[str, Any]:
            out: Dict[str, Any] = {}
            for k, v in self.__dict__.items():
                if exclude_none and v is None:
                    continue
                if isinstance(v, BaseModel):
                    out[k] = v.model_dump(exclude_none=exclude_none)
                elif isinstance(v, list):
                    out[k] = [
                        item.model_dump(exclude_none=exclude_none)
                        if isinstance(item, BaseModel) else item
                        for item in v
                    ]
                else:
                    out[k] = v
            return out

    _HAS_PYDANTIC = False


# ---------------------------------------------------------------------------
# AgentCard  —  served at /.well-known/agent.json
# ---------------------------------------------------------------------------
class AgentProvider(BaseModel):
    """Identifies the organization providing the agent."""
    organization: str
    url: Optional[str] = None


class AgentCapabilities(BaseModel):
    """Declares which optional A2A features the agent supports."""
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = False


class AgentAuthentication(BaseModel):
    """Authentication requirements for invoking the agent."""
    schemes: List[str] = Field(default_factory=list)
    credentials: Optional[str] = None


class AgentSkill(BaseModel):
    """A single capability exposed via this agent."""
    id: str
    name: str
    description: str
    tags: List[str] = Field(default_factory=list)
    examples: List[str] = Field(default_factory=list)
    inputModes: List[str] = Field(default_factory=lambda: ["application/json"])
    outputModes: List[str] = Field(default_factory=lambda: ["application/json"])


class AgentCard(BaseModel):
    """
    The Agent Card / `/.well-known/agent.json` manifest.

    Required fields per A2A spec v0.1.0: name, url, version, capabilities, skills.
    """
    name: str
    description: str
    url: str
    provider: AgentProvider
    version: str
    capabilities: AgentCapabilities
    authentication: AgentAuthentication
    defaultInputModes: List[str] = Field(default_factory=lambda: ["application/json"])
    defaultOutputModes: List[str] = Field(default_factory=lambda: ["application/json"])
    skills: List[AgentSkill] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Message & Part  —  content exchanged in tasks/send requests
# ---------------------------------------------------------------------------
class TextPart(BaseModel):
    """A text segment of a message."""
    type: str = "text"
    text: str = ""


class DataPart(BaseModel):
    """A structured-data segment of a message."""
    type: str = "data"
    data: Dict[str, Any] = Field(default_factory=dict)


class FilePart(BaseModel):
    """A file segment of a message (bytes or URI reference)."""
    type: str = "file"
    file: Dict[str, Any] = Field(default_factory=dict)


Part = Union[TextPart, DataPart, FilePart]


class Message(BaseModel):
    """An A2A message (user or agent)."""
    role: str  # "user" | "agent"
    parts: List[Dict[str, Any]] = Field(default_factory=list)
    messageId: Optional[str] = None
    taskId: Optional[str] = None
    contextId: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Task & Artifact  —  response payload from tasks/send
# ---------------------------------------------------------------------------
class TaskStatus(BaseModel):
    """Status envelope for an A2A Task."""
    state: str  # "submitted" | "working" | "completed" | "failed" | "canceled" | "input-required"
    message: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class Artifact(BaseModel):
    """An artifact returned by an A2A agent."""
    artifactId: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    parts: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class Task(BaseModel):
    """The Task object returned by tasks/send (or streamed via tasks/sendSubscribe)."""
    id: str
    contextId: Optional[str] = None
    status: TaskStatus
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    kind: str = "task"


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 envelope used by A2A
# ---------------------------------------------------------------------------
class JsonRpcError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)
    id: Optional[Union[str, int]] = None


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# JSON-RPC error codes used by A2A
# ---------------------------------------------------------------------------
# Standard JSON-RPC codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603
# A2A-specific codes
TASK_NOT_FOUND = -32001
TASK_NOT_CANCELABLE = -32002
PUSH_NOTIFICATION_NOT_SUPPORTED = -32003
UNSUPPORTED_OPERATION = -32004


def build_error(request_id, code: int, message: str, data: Any = None) -> Dict[str, Any]:
    """Build a JSON-RPC 2.0 error response body."""
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": err}


def build_result(request_id, result: Any) -> Dict[str, Any]:
    """Build a JSON-RPC 2.0 success response body."""
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


__all__ = [
    "AgentCard",
    "AgentProvider",
    "AgentCapabilities",
    "AgentAuthentication",
    "AgentSkill",
    "Message",
    "TextPart",
    "DataPart",
    "FilePart",
    "Task",
    "TaskStatus",
    "Artifact",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "JsonRpcError",
    "build_error",
    "build_result",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
    "TASK_NOT_FOUND",
    "UNSUPPORTED_OPERATION",
]
