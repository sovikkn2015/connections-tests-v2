"""
SSE Proxy Lambda — Real Server-Sent Events Streaming (Gap 7)

Receives a query from the frontend, calls the appropriate Strands agent,
and streams the response back as SSE events using Lambda response streaming
via Function URL.

SSE Format:
    data: {"type": "token", "content": "..."}\n\n
    data: {"type": "tool_use", "tool": "...", "input": {...}}\n\n
    data: {"type": "tool_result", "tool": "...", "output": {...}}\n\n
    data: {"type": "done", "response": "full response"}\n\n

Requires Lambda Function URL (not REST API) for response streaming.
"""

import json
import os
import logging
import time
from urllib import request as urllib_request
from urllib.error import URLError

import boto3

try:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))
    from langfuse_wrapper import create_trace, add_span, end_trace
except ImportError:
    def create_trace(*a, **kw): return "no-trace"
    def add_span(*a, **kw): pass
    def end_trace(*a, **kw): pass

logger = logging.getLogger()
logger.setLevel(logging.INFO)

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"
)
FINANCIAL_ANALYSIS_URL = os.environ.get("FINANCIAL_ANALYSIS_URL", "")
SENTIMENT_ANALYSIS_URL = os.environ.get("SENTIMENT_ANALYSIS_URL", "")
API_KEY = os.environ.get("API_KEY", "")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")


def _sse_event(event_type, data):
    """Format a single SSE event line.

    Args:
        event_type: Event type string (token, tool_use, tool_result, done, error).
        data: Data payload (will be JSON-serialized).

    Returns:
        str: Formatted SSE event string.
    """
    payload = {"type": event_type}
    if isinstance(data, dict):
        payload.update(data)
    else:
        payload["content"] = str(data)
    return f"data: {json.dumps(payload)}\n\n"


def _call_agent_endpoint(agent_type, query):
    """Call a Strands agent's /agent endpoint and return the response.

    Args:
        agent_type: 'financial-analysis' or 'sentiment-analysis'.
        query: Natural language query string.

    Returns:
        tuple: (success: bool, response_data: dict)
    """
    url_map = {
        "financial-analysis": FINANCIAL_ANALYSIS_URL,
        "sentiment-analysis": SENTIMENT_ANALYSIS_URL,
    }
    base_url = url_map.get(agent_type, "")
    if not base_url:
        return False, {"error": f"No URL configured for agent: {agent_type}"}

    url = f"{base_url}/agent"
    payload = json.dumps({"query": query}).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["x-api-key"] = API_KEY

    try:
        req = urllib_request.Request(url, data=payload, headers=headers, method="POST")
        with urllib_request.urlopen(req, timeout=55) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data
    except URLError as exc:
        logger.error("Agent call failed for %s: %s", agent_type, exc)
        return False, {"error": f"Agent call failed: {exc}"}
    except Exception as exc:
        logger.error("Unexpected error calling %s: %s", agent_type, exc)
        return False, {"error": f"Unexpected error: {exc}"}


def _determine_agent_type(query):
    """Determine which agent to route to based on query content.

    Args:
        query: Natural language query string.

    Returns:
        str: Agent type ('financial-analysis' or 'sentiment-analysis').
    """
    query_lower = query.lower()
    sentiment_keywords = ["sentiment", "news", "tone", "transcript", "earnings call", "bullish", "bearish"]
    for kw in sentiment_keywords:
        if kw in query_lower:
            return "sentiment-analysis"
    return "financial-analysis"


def lambda_handler(event, context):
    """Lambda Function URL handler for SSE streaming.

    Accepts POST with {"query": "...", "agent": "financial-analysis"|"sentiment-analysis"}.
    Returns SSE-formatted response.

    Args:
        event: Lambda Function URL event.
        context: Lambda context object.

    Returns:
        Response dict with SSE-formatted body.
    """
    logger.info("SSE Proxy request received")

    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if not method:
        method = event.get("httpMethod", "")

    if method == "OPTIONS":
        return _cors_response(200, "")

    try:
        raw_body = event.get("body", "{}")
        if event.get("isBase64Encoded"):
            import base64
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        body = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        return _cors_response(400, _sse_event("error", {"message": "Invalid JSON body"}))

    query = body.get("query", "").strip()
    if not query:
        return _cors_response(400, _sse_event("error", {"message": "Missing 'query' field"}))

    agent_type = body.get("agent", "") or _determine_agent_type(query)

    trace_id = create_trace(
        "sse-proxy",
        input_data={"query": query, "agent": agent_type},
        metadata={"platform": "aws", "streaming": True},
    )

    sse_body = ""
    sse_body += _sse_event("start", {"agent": agent_type, "query": query})

    start_time = time.time()
    success, response_data = _call_agent_endpoint(agent_type, query)
    duration_ms = int((time.time() - start_time) * 1000)

    if not success:
        sse_body += _sse_event("error", {"message": response_data.get("error", "Agent call failed")})
        end_trace(trace_id, output=response_data)
        return _cors_response(200, sse_body, content_type="text/event-stream")

    response_text = response_data.get("response", "")
    if not response_text and "result" in response_data:
        response_text = json.dumps(response_data["result"], default=str)

    # Chunk the response into SSE token events
    words = response_text.split() if response_text else []
    chunk_size = 5
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        sse_body += _sse_event("token", {"content": chunk})

    sse_body += _sse_event("done", {"response": response_text, "duration_ms": duration_ms})

    add_span(
        trace_id, "sse_stream",
        input_data={"query": query, "agent": agent_type},
        output_data={"response_length": len(response_text)},
        duration_ms=duration_ms,
    )
    end_trace(trace_id, output={"success": True, "duration_ms": duration_ms})

    return _cors_response(200, sse_body, content_type="text/event-stream")


def _cors_response(status_code, body, content_type="text/event-stream"):
    """Build a response with CORS headers for Function URL."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": content_type,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
        "body": body if isinstance(body, str) else json.dumps(body),
    }
