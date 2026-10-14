"""V3 agent-proxy-async Lambda — async submit-and-poll for long advisor turns.

Architecture
------------
API Gateway integration timeout is 29s. Advisor action_write runs the 7-gate
serial trust spine + LLM planning, typically 40-90s, so it always 504s on
the standard /agent/invoke path.

This Lambda exposes two routes:

  POST /agent/invoke-long
    Returns {turn_id, status: "pending"} in <1s, triggers an ASYNC invoke
    (InvocationType=Event) of itself to do the real work.

  GET  /agent/invoke-long/status/{turn_id}
    Returns the current status:
      - {"status": "pending"} if the worker hasn't written a result yet
      - {"status": "ok", "envelope": {...}} when the envelope is ready
      - {"status": "error", "error": {...}} if the worker errored

Result storage
--------------
Worker writes the envelope (or error) to S3 under
`s3://${RESULTS_BUCKET}/turns/{turn_id}.json` with 24-hour lifecycle.
GET reads from the same bucket.

Worker pathway
--------------
The Lambda recognizes the async invoke (no requestContext.http) and runs
`_run_turn_and_write()` which calls AgentCore identically to the sync
path and stores the envelope on S3. Max Lambda execution time is 5 min
(plenty for action_write).

Frontend integration
--------------------
HttpAgentTransport detects advisor + action-verb and routes through the
async path: POST once, poll every 500ms until status != pending. Applies
the envelope exactly like the sync path.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import secrets
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AGENTCORE_RUNTIME_ARN = os.environ.get("AGENTCORE_RUNTIME_ARN", "")
AGENTCORE_REGION = os.environ.get(
    "AGENTCORE_REGION", os.environ.get("AWS_REGION", "us-east-1")
)
CORS_ALLOW = os.environ.get("CORS_ALLOW_ORIGIN", "*")
DEV_MODE = os.environ.get("MCP_DEV_MODE", "true").lower() == "true"
RESULTS_BUCKET = os.environ.get("RESULTS_BUCKET", "")
SELF_FUNCTION_NAME = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "")


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": CORS_ALLOW,
        "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Session-Token",
        "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    }


def _respond(status: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            **_cors_headers(),
        },
        "body": json.dumps(body) if not isinstance(body, str) else body,
    }


def _extract_bearer(headers: dict[str, str]) -> str | None:
    for k in ("authorization", "Authorization"):
        v = headers.get(k, "")
        if v.startswith("Bearer "):
            return v[7:].strip()
    for k in ("x-session-token", "X-Session-Token"):
        v = headers.get(k, "")
        if v:
            return v.strip()
    return None


def _turn_key(turn_id: str) -> str:
    # Defensive: clamp turn_id to alphanum + hyphen to avoid S3 key traversal
    safe = "".join(c for c in turn_id if c.isalnum() or c in "-_")[:128]
    return f"turns/{safe}.json"


def _s3() -> Any:
    return boto3.client("s3", region_name=AGENTCORE_REGION)


def lambda_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    # ------------------------------------------------------------------
    # Async invocation path — no requestContext, body is the worker job.
    # ------------------------------------------------------------------
    if not event.get("requestContext") and event.get("__worker__"):
        return _run_turn_and_write(event)

    request_context = event.get("requestContext", {}) or {}
    method = (
        event.get("httpMethod")
        or request_context.get("http", {}).get("method", "")
        or ""
    ).upper()
    path = (event.get("rawPath") or event.get("path") or "") or ""

    if method == "OPTIONS":
        return {"statusCode": 204, "headers": _cors_headers(), "body": ""}

    if not AGENTCORE_RUNTIME_ARN:
        return _respond(
            500, {"status": "error", "error": {"message": "AGENTCORE_RUNTIME_ARN not configured"}}
        )
    if not RESULTS_BUCKET:
        return _respond(
            500, {"status": "error", "error": {"message": "RESULTS_BUCKET not configured"}}
        )

    headers = event.get("headers") or {}
    token = _extract_bearer(headers)
    if not token and not DEV_MODE:
        return _respond(401, {"status": "error", "error": {"message": "Missing bearer"}})

    # Route: GET /agent/invoke-long/status/{turn_id}
    if method == "GET" and "/status/" in path:
        turn_id = path.rsplit("/", 1)[-1]
        return _read_status(turn_id)

    # Route: POST /agent/invoke-long — submit async
    if method == "POST":
        raw_body = event.get("body") or ""
        if event.get("isBase64Encoded"):
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        try:
            body = json.loads(raw_body) if raw_body else {}
        except json.JSONDecodeError:
            return _respond(400, {"status": "error", "error": {"message": "body must be JSON"}})

        prompt = body.get("prompt") or body.get("message") or ""
        if not isinstance(prompt, str) or not prompt.strip():
            return _respond(400, {"status": "error", "error": {"message": "'prompt' required"}})

        # Generate a turn_id we own so the caller can poll
        turn_id = str(body.get("turn_id") or body.get("correlation_id") or f"t-{secrets.token_urlsafe(16)}")

        # Write an initial "pending" marker so GET doesn't 404 race with the
        # async invoke warm-up.
        _write_pending(turn_id)

        # Fire-and-forget self-invoke with the payload under a __worker__ flag
        # so the handler routes to the worker path.
        job = {
            "__worker__": True,
            "turn_id": turn_id,
            "prompt": prompt,
            "persona": str(body.get("persona") or "fsi_advisor"),
            "principal_id": str(
                body.get("principal_id") or body.get("principalId") or "dev-principal"
            ),
            "session_id": str(
                body.get("session_id")
                or body.get("sessionKey")
                or f"async-{int(time.time() * 1000)}"
            ),
            "correlation_id": str(
                body.get("correlation_id") or body.get("correlationId") or turn_id
            ),
            "turn_number": int(body.get("turn_number") or 1),
        }
        if len(job["session_id"]) < 33:
            job["session_id"] = f"{job['session_id']}-{secrets.token_hex(16)}"

        try:
            boto3.client("lambda", region_name=AGENTCORE_REGION).invoke(
                FunctionName=SELF_FUNCTION_NAME,
                InvocationType="Event",
                Payload=json.dumps(job).encode("utf-8"),
            )
        except ClientError as exc:
            logger.exception("async self-invoke failed")
            return _respond(
                500,
                {
                    "status": "error",
                    "error": {"message": f"async invoke failed: {exc}"[:400]},
                },
            )

        return _respond(202, {"status": "pending", "turn_id": turn_id})

    return _respond(404, {"status": "error", "error": {"message": "not found"}})


# ----------------------------------------------------------------------
# Worker — runs the real AgentCore call and writes envelope to S3.
# ----------------------------------------------------------------------

def _run_turn_and_write(job: dict[str, Any]) -> dict[str, Any]:
    turn_id = job.get("turn_id", "")
    start = time.time()
    try:
        envelope = _invoke_agentcore_sync(
            prompt=job["prompt"],
            persona=job["persona"],
            principal_id=job["principal_id"],
            session_id=job["session_id"],
            correlation_id=job["correlation_id"],
            turn_number=int(job.get("turn_number", 1)),
        )
        _write_result(
            turn_id,
            {
                "status": "ok",
                "envelope": envelope,
                "duration_ms": int((time.time() - start) * 1000),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("worker failed")
        _write_result(
            turn_id,
            {
                "status": "error",
                "error": {"type": type(exc).__name__, "message": str(exc)[:500]},
                "duration_ms": int((time.time() - start) * 1000),
            },
        )
    return {"statusCode": 200, "body": "{}"}


def _invoke_agentcore_sync(
    *,
    prompt: str,
    persona: str,
    principal_id: str,
    session_id: str,
    correlation_id: str,
    turn_number: int,
) -> dict[str, Any]:
    payload_bytes = json.dumps(
        {
            "prompt": prompt,
            "persona": persona,
            "principal_id": principal_id,
            "session_id": session_id,
            "correlation_id": correlation_id,
            "turn_number": turn_number,
        }
    ).encode("utf-8")
    client = boto3.client("bedrock-agentcore", region_name=AGENTCORE_REGION)
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=AGENTCORE_RUNTIME_ARN,
        runtimeSessionId=session_id,
        contentType="application/json",
        accept="application/json",
        payload=payload_bytes,
    )
    body_stream = resp.get("response") or resp.get("payload") or b""
    if hasattr(body_stream, "read"):
        body_bytes = body_stream.read()
    else:
        body_bytes = (
            body_stream
            if isinstance(body_stream, (bytes, bytearray))
            else str(body_stream).encode("utf-8")
        )
    try:
        return json.loads(body_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "ok", "text": body_bytes.decode("utf-8", errors="replace")}


# ----------------------------------------------------------------------
# S3 read/write helpers
# ----------------------------------------------------------------------

def _write_pending(turn_id: str) -> None:
    try:
        _s3().put_object(
            Bucket=RESULTS_BUCKET,
            Key=_turn_key(turn_id),
            Body=json.dumps({"status": "pending", "turn_id": turn_id}).encode("utf-8"),
            ContentType="application/json",
        )
    except ClientError:
        logger.exception("s3 put pending failed")


def _write_result(turn_id: str, result: dict[str, Any]) -> None:
    try:
        _s3().put_object(
            Bucket=RESULTS_BUCKET,
            Key=_turn_key(turn_id),
            Body=json.dumps(result).encode("utf-8"),
            ContentType="application/json",
        )
    except ClientError:
        logger.exception("s3 put result failed")


def _read_status(turn_id: str) -> dict[str, Any]:
    try:
        obj = _s3().get_object(Bucket=RESULTS_BUCKET, Key=_turn_key(turn_id))
        body = obj["Body"].read().decode("utf-8")
        return _respond(200, json.loads(body))
    except _s3().exceptions.NoSuchKey:
        return _respond(404, {"status": "error", "error": {"message": "unknown turn_id"}})
    except ClientError as exc:
        logger.exception("s3 get failed")
        return _respond(500, {"status": "error", "error": {"message": str(exc)[:400]}})
