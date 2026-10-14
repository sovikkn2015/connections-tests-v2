"""
Langfuse tracing wrapper for AWS Lambda agents.

Reads Langfuse credentials from environment variables.
Falls back gracefully if Langfuse is not configured — tracing calls
become no-ops so agent logic is never blocked by observability failures.

Usage:
    from shared.langfuse_wrapper import create_trace, add_span, add_generation

    trace_id = create_trace("financial-analysis", input_data={"ticker": "NVDA"})
    add_span(trace_id, "run_dcf", input_data={...}, output_data={...}, duration_ms=320)
    add_generation(trace_id, "fair_value_narrative", model="claude-sonnet-4",
                   input_data="prompt...", output_data="response...",
                   usage={"promptTokens": 800, "completionTokens": 400})
"""

import os
import json
import logging
import time
import uuid
import base64
from datetime import datetime, timezone
from urllib import request as urllib_request
from urllib.error import URLError

logger = logging.getLogger(__name__)

LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "")
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")

INGESTION_PATH = "/api/public/ingestion"
TIMEOUT_SECONDS = 5


def is_configured():
    """Check whether Langfuse credentials are present in the environment."""
    return bool(LANGFUSE_HOST and LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)


def _auth_header():
    """Build Basic auth header from public_key:secret_key."""
    credentials = f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}"
    encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


def _iso_now():
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _event_id():
    """Generate a unique event ID."""
    return str(uuid.uuid4())


def _build_event(event_type, body):
    """Wrap a body dict in the Langfuse batch event envelope."""
    return {
        "id": _event_id(),
        "type": event_type,
        "timestamp": _iso_now(),
        "body": body,
    }


def _post_ingestion(events):
    """POST a batch of events to the Langfuse ingestion API.

    Uses only urllib (no external dependencies) so this works in any
    Lambda runtime without adding packages.
    """
    if not is_configured():
        logger.debug("Langfuse not configured — skipping ingestion")
        return

    url = f"{LANGFUSE_HOST.rstrip('/')}{INGESTION_PATH}"
    payload = json.dumps({
        "batch": events,
        "metadata": {
            "sdk_name": "aws-lambda-python",
            "sdk_version": "1.0.0",
        },
    }).encode("utf-8")

    req = urllib_request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": _auth_header(),
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            if resp.status >= 300:
                logger.warning("Langfuse ingestion returned %d", resp.status)
    except URLError as exc:
        logger.warning("Langfuse ingestion failed: %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse ingestion unexpected error: %s", exc)


# ---- Public API ----

def create_trace(name, input_data=None, metadata=None):
    """Create a new Langfuse trace and return its trace_id.

    Args:
        name: Trace name (e.g. "financial-analysis", "sentiment-analysis").
        input_data: The input payload (dict, str, or None).
        metadata: Optional dict of extra metadata tags.

    Returns:
        str: The generated trace_id (usable even if Langfuse is not configured).
    """
    trace_id = f"ir-{uuid.uuid4().hex[:12]}-{int(time.time() * 1000)}"

    body = {
        "id": trace_id,
        "name": name,
        "input": input_data,
        "metadata": metadata or {},
    }
    _post_ingestion([_build_event("trace-create", body)])
    return trace_id


def add_span(trace_id, name, input_data=None, output_data=None, duration_ms=None, metadata=None):
    """Add a span to an existing trace.

    Args:
        trace_id: The parent trace ID.
        name: Span name (e.g. "run_dcf", "callout_sec_edgar").
        input_data: Input payload for this span.
        output_data: Output payload for this span.
        duration_ms: Duration in milliseconds (optional).
        metadata: Optional dict of extra metadata.
    """
    body = {
        "id": _event_id(),
        "traceId": trace_id,
        "name": name,
        "input": input_data,
        "output": output_data,
        "metadata": metadata or {},
    }

    if duration_ms is not None:
        end_time = datetime.now(timezone.utc)
        start_ms = int(end_time.timestamp() * 1000) - duration_ms
        start_time = datetime.fromtimestamp(start_ms / 1000, tz=timezone.utc)
        body["startTime"] = start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        body["endTime"] = end_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    _post_ingestion([_build_event("span-create", body)])


def add_generation(trace_id, name, model, input_data=None, output_data=None, usage=None):
    """Add a generation event to a trace (for LLM calls).

    Args:
        trace_id: The parent trace ID.
        name: Generation name (e.g. "fair_value_narrative").
        model: Model identifier (e.g. "claude-sonnet-4").
        input_data: The prompt / input sent to the model.
        output_data: The model's response.
        usage: Optional dict with keys promptTokens, completionTokens, totalTokens.
    """
    body = {
        "id": _event_id(),
        "traceId": trace_id,
        "name": name,
        "model": model,
        "input": input_data,
        "output": output_data,
    }

    if usage:
        body["usage"] = usage

    _post_ingestion([_build_event("generation-create", body)])


def end_trace(trace_id, output=None, metadata=None):
    """Update a trace with final output and metadata.

    Args:
        trace_id: The trace ID to update.
        output: Final output payload.
        metadata: Optional dict of final metadata.
    """
    body = {
        "id": trace_id,
        "output": output,
        "metadata": metadata or {},
    }
    _post_ingestion([_build_event("trace-create", body)])


def get_prompt(name, fallback):
    """Fetch a prompt from the Langfuse prompt registry.

    Falls back to the provided default if Langfuse is not configured or
    the prompt cannot be retrieved.

    Args:
        name: Prompt name in Langfuse (e.g. "financial-analysis-fair-value").
        fallback: Default prompt text to use if fetch fails.

    Returns:
        str: The prompt text from Langfuse, or the fallback.
    """
    if not is_configured():
        return fallback
    try:
        url = f"{LANGFUSE_HOST.rstrip('/')}/api/public/v2/prompts/{name}"
        req = urllib_request.Request(
            url,
            headers={"Authorization": _auth_header()},
            method="GET",
        )
        with urllib_request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("prompt", fallback)
    except Exception as exc:
        logger.warning("Langfuse prompt fetch failed for '%s': %s", name, exc)
        return fallback
