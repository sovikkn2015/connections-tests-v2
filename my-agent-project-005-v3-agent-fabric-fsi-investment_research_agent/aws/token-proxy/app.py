"""
OAuth2 Token Proxy — handles Salesforce token exchange server-side to avoid CORS.

Routes:
  POST /oauth/agent-token  → ECA client_credentials grant (chatbot_api scope)
  POST /oauth/token         → PKCE authorization_code exchange (existing)
"""
import json
import os
import logging
import base64
from urllib import request as urllib_request
from urllib.parse import urlencode, parse_qs

logger = logging.getLogger()
logger.setLevel(logging.INFO)

SF_TOKEN_URL = os.environ.get("SF_TOKEN_URL", "https://login.salesforce.com/services/oauth2/token")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")

# ECA (External Client App) credentials for Agent API tokens
ECA_CLIENT_ID = os.environ.get("ECA_CLIENT_ID", "")
ECA_CLIENT_SECRET = os.environ.get("ECA_CLIENT_SECRET", "")


def lambda_handler(event, context):
    logger.info("Method: %s, Path: %s", event.get("httpMethod"), event.get("path"))

    if event.get("httpMethod") == "OPTIONS":
        return cors_response(200, "")

    # ── Route: ECA agent token (client_credentials) ──
    path = event.get("path", "") or event.get("resource", "")
    if path.endswith("agent-token"):
        return _handle_agent_token()

    # ── Route: PKCE token exchange (existing) ──
    return _handle_pkce_token(event)


def _handle_agent_token():
    """Mint an ECA token using client_credentials grant for Agent API access."""
    try:
        if not ECA_CLIENT_ID or not ECA_CLIENT_SECRET:
            return cors_response(500, json.dumps({
                "error": "ECA_CLIENT_ID and ECA_CLIENT_SECRET must be configured"
            }))

        form_data = urlencode({
            "grant_type": "client_credentials",
            "client_id": ECA_CLIENT_ID,
            "client_secret": ECA_CLIENT_SECRET,
        }).encode("utf-8")

        req = urllib_request.Request(
            SF_TOKEN_URL,
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urllib_request.urlopen(req, timeout=15) as resp:
            token_data = json.loads(resp.read().decode())
            logger.info("ECA token minted successfully")
            return cors_response(200, json.dumps(token_data))
    except Exception as e:
        logger.error("ECA token error: %s", str(e))
        return cors_response(400, json.dumps({"error": str(e)}))


def _handle_pkce_token(event):
    """Exchange a PKCE authorization code for an access token (existing logic)."""
    try:
        raw_body = event.get("body", "")
        if event.get("isBase64Encoded"):
            raw_body = base64.b64decode(raw_body).decode("utf-8")

        content_type = ""
        for k, v in (event.get("headers") or {}).items():
            if k.lower() == "content-type":
                content_type = v.lower()
                break

        if "json" in content_type:
            params = json.loads(raw_body)
        else:
            parsed = parse_qs(raw_body, keep_blank_values=True)
            params = {k: v[0] for k, v in parsed.items()}

        logger.info("Keys: %s", list(params.keys()))

        form_data = urlencode({
            "grant_type": params.get("grant_type", "authorization_code"),
            "code": params.get("code", ""),
            "client_id": params.get("client_id", ""),
            "redirect_uri": params.get("redirect_uri", ""),
            "code_verifier": params.get("code_verifier", ""),
        }).encode("utf-8")

        req = urllib_request.Request(SF_TOKEN_URL, data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with urllib_request.urlopen(req, timeout=15) as resp:
            token_data = json.loads(resp.read().decode())
            return cors_response(200, json.dumps(token_data))
    except Exception as e:
        logger.error("Token proxy error: %s", str(e))
        return cors_response(400, json.dumps({"error": str(e)}))


def cors_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
        "body": body if isinstance(body, str) else json.dumps(body),
    }
