"""
Agent Query Proxy — Lambda handler.
Proxies frontend queries to the AgentCore agent via bedrock-agentcore SDK.

Flow: Browser → POST /agent/query (API Gateway) → this Lambda → AgentCore → OpenClaw → response

Uses bedrock-agentcore invoke_agent_runtime (NOT bedrock-agent-runtime).
The agent runtime ARN is constructed from AGENTCORE_AGENT_ID + account ID from STS.
"""
import json
import logging
import os
import uuid

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CORS_ORIGIN = os.environ["CORS_ALLOW_ORIGIN"]
AGENT_ID = os.environ["AGENTCORE_AGENT_ID"]  # e.g. fsi_research_agent-Sr1m3j3MUh
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Derive account ID from STS at cold start (no hardcoded account IDs)
_sts = boto3.client("sts", region_name=AWS_REGION)
ACCOUNT_ID = _sts.get_caller_identity()["Account"]

# Construct the full ARN for the AgentCore runtime
AGENT_RUNTIME_ARN = (
    f"arn:aws:bedrock-agentcore:{AWS_REGION}:{ACCOUNT_ID}:runtime/{AGENT_ID}"
)
logger.info("Agent proxy initialized: arn=%s", AGENT_RUNTIME_ARN)

client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)


def _cors_headers():
    return {
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    }


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _ensure_session_id(session_key):
    """Ensure session ID meets AgentCore's 33-char minimum (UUID format)."""
    if len(session_key) >= 33:
        return session_key
    # Generate a deterministic UUID from the session key so the same key
    # always maps to the same session ID (preserves conversation context).
    return str(uuid.uuid5(uuid.NAMESPACE_URL, session_key))


def lambda_handler(event, context):
    """AWS Lambda entry point — proxies agent queries to AgentCore."""
    method = event.get(
        "httpMethod",
        event.get("requestContext", {}).get("http", {}).get("method", "GET"),
    ).upper()

    # CORS preflight
    if method == "OPTIONS":
        return _response(200, {})

    if method != "POST":
        return _response(405, {"error": "Method not allowed"})

    try:
        body = json.loads(event.get("body", "{}"))
    except json.JSONDecodeError:
        return _response(400, {"error": "Invalid JSON"})

    message = body.get("message", "")
    session_key = body.get("sessionKey", "default")

    if not message:
        return _response(400, {"error": "Missing message"})

    runtime_session_id = _ensure_session_id(session_key)
    logger.info(
        "Invoking AgentCore runtime %s session=%s (runtime_session=%s)",
        AGENT_ID, session_key, runtime_session_id,
    )

    try:
        # Payload format per AWS docs: {"prompt": "..."}
        payload = json.dumps({"prompt": message}).encode("utf-8")

        resp = client.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            runtimeSessionId=runtime_session_id,
            contentType="application/json",
            accept="text/event-stream",
            payload=payload,
        )

        content_type = resp.get("contentType", "")
        response_obj = resp.get("response")

        # Collect both the final text AND structured tool events from the SSE stream.
        # The frontend needs tool results to hydrate the research panel.
        text_chunks = []
        tool_results = []

        if "text/event-stream" in content_type:
            for line in response_obj.iter_lines(chunk_size=1024):
                if not line:
                    continue
                decoded = line.decode("utf-8")
                if not decoded.startswith("data: "):
                    continue
                data_str = decoded[6:]
                # Try to parse as JSON to extract tool events
                try:
                    evt = json.loads(data_str)
                    if isinstance(evt, dict):
                        stream = evt.get("stream")
                        d = evt.get("data", evt)
                        if stream == "tool" and d.get("phase") == "result":
                            tool_results.append({
                                "name": d.get("name", ""),
                                "toolCallId": d.get("toolCallId", ""),
                                "result": d.get("result"),
                            })
                        elif stream == "tool" and d.get("phase") == "start":
                            tool_results.append({
                                "name": d.get("name", ""),
                                "toolCallId": d.get("toolCallId", ""),
                                "phase": "start",
                                "input": d.get("input"),
                            })
                        elif stream == "assistant" and d.get("text"):
                            text_chunks.append(d["text"])
                        else:
                            # Unstructured data line — treat as text
                            text_chunks.append(data_str)
                    else:
                        text_chunks.append(data_str)
                except json.JSONDecodeError:
                    text_chunks.append(data_str)
            result_text = "".join(text_chunks)
        else:
            # Standard response — read full body
            response_body = response_obj.read().decode("utf-8")
            logger.info(
                "AgentCore response contentType=%s len=%d",
                content_type, len(response_body),
            )
            try:
                parsed = json.loads(response_body)
                if isinstance(parsed, dict):
                    result_text = parsed.get(
                        "response", parsed.get("text", response_body)
                    )
                    # Check if the parsed response itself contains tool results
                    if "toolResults" in parsed:
                        tool_results = parsed["toolResults"]
                else:
                    result_text = response_body
            except json.JSONDecodeError:
                result_text = response_body

        response_body_out = {
            "response": result_text,
            "sessionKey": session_key,
        }
        # Only include toolResults if we captured any (keeps backward compat)
        if tool_results:
            response_body_out["toolResults"] = tool_results

        return _response(200, response_body_out)
    except Exception as e:
        logger.exception("AgentCore invoke failed")
        return _response(502, {"error": str(e)})
