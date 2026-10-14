"""
M12 Agent Runtime — FastAPI application.

Endpoints:
  POST /agent/chat   — Send message, get agent response
  GET  /agent/stream — SSE streaming agent response
  GET  /health       — Health check

Integrates with M6 web_api.py (web_api calls this for agent responses).
AID token from Authorization header → tools context for M6 calls.

No cross-module imports (Rule 9). No credentials in code (Rule 20).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from .agent_factory import create_agent
from .config import AGENT_VERSION, M6_GATEWAY_URL
from .tools.m6_tools import current_aid_token

logger = logging.getLogger("m12.app")

# ── Request / Response Models ────────────────────────────────────


class ChatRequest(BaseModel):
    """Incoming chat message."""
    message: str = Field(..., min_length=1, max_length=10000)
    aid_token: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Agent response."""
    response: str
    conversation_id: Optional[str] = None
    agent_version: str = AGENT_VERSION
    latency_ms: int = 0


class StreamRequest(BaseModel):
    """SSE streaming request."""
    message: str = Field(..., min_length=1, max_length=10000)
    aid_token: str = Field(..., min_length=1)


# ── Agent singleton ──────────────────────────────────────────────

_agent = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize agent at startup."""
    global _agent
    _agent = create_agent()
    logger.info("M12 Agent Runtime started (version=%s)", AGENT_VERSION)
    yield
    logger.info("M12 Agent Runtime stopped")


# ── FastAPI App ──────────────────────────────────────────────────

app = FastAPI(
    title="M12 Agent Runtime",
    description="Strands SDK agentic core for Project 007",
    version="0.1.0",
    lifespan=lifespan,
)


# ── POST /agent/chat ─────────────────────────────────────────────


@app.post("/agent/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest) -> ChatResponse:
    """Send a message to the agent and get a response."""
    global _agent
    if _agent is None:
        _agent = create_agent()

    # Set AID token in context for tool calls to M6
    token = current_aid_token.set(request.aid_token)
    start = time.monotonic()

    try:
        # Run agent in thread pool (Strands agents are synchronous)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: _agent(request.message)
        )
        elapsed_ms = int((time.monotonic() - start) * 1000)

        return ChatResponse(
            response=str(result),
            conversation_id=request.conversation_id,
            agent_version=AGENT_VERSION,
            latency_ms=elapsed_ms,
        )
    except Exception as exc:
        logger.error("Agent error: %s", exc)
        # Generic error to client (Rule 9)
        raise HTTPException(
            status_code=500,
            detail="Agent temporarily unavailable",
        )
    finally:
        current_aid_token.reset(token)


# ── GET /agent/stream — SSE Streaming ────────────────────────────


@app.post("/agent/stream")
async def agent_stream(request: StreamRequest) -> StreamingResponse:
    """Stream agent response as Server-Sent Events."""
    global _agent
    if _agent is None:
        _agent = create_agent()

    token = current_aid_token.set(request.aid_token)

    async def event_generator():
        try:
            loop = asyncio.get_event_loop()
            # Run agent and stream result chunks
            result = await loop.run_in_executor(
                None, lambda: _agent(request.message)
            )
            # Yield the complete response as SSE
            text = str(result)
            # Stream in chunks for responsiveness
            chunk_size = 100
            for i in range(0, len(text), chunk_size):
                chunk = text[i:i + chunk_size]
                yield f"data: {json.dumps({'text': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("Stream error: %s", exc)
            yield f"data: {json.dumps({'error': 'Agent temporarily unavailable'})}\n\n"
        finally:
            current_aid_token.reset(token)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ── GET /health ──────────────────────────────────────────────────


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "module": "m12-agent-runtime",
        "version": "0.1.0",
        "agent_version": AGENT_VERSION,
        "m6_gateway_url": M6_GATEWAY_URL,
    }
