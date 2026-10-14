"""
Salesforce OAuth Token Proxy — Lambda handler.

Proxies the OAuth2 PKCE token exchange to Salesforce server-side,
bypassing the CORS restriction on Salesforce's /services/oauth2/token endpoint.

The frontend (CloudFront SPA) sends the auth code + code_verifier here,
and this Lambda forwards them to Salesforce and returns the token response.

No secrets stored — the Connected App uses PKCE (no client_secret needed).
"""

import json
import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# CORS origin from environment (locked down, not wildcard)
CORS_ORIGIN = os.environ.get("CORS_ALLOW_ORIGIN", "http://localhost:5173")

# Salesforce token endpoint base
SF_TOKEN_URL = os.environ.get("SF_TOKEN_URL", "https://login.salesforce.com/services/oauth2/token")


def _cors_headers():
    return {
        "Access-Control-Allow-Origin": CORS_ORIGIN,
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
    }


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    """AWS Lambda entry point — proxies token exchange to Salesforce."""
    method = event.get("httpMethod", "GET").upper()

    # CORS preflight
    if method == "OPTIONS":
        return _response(200, {})

    if method != "POST":
        return _response(405, {"error": "Method not allowed"})

    # Parse the incoming request body (application/x-www-form-urlencoded or JSON)
    content_type = ""
    headers = event.get("headers") or {}
    for k, v in headers.items():
        if k.lower() == "content-type":
            content_type = v.lower()
            break

    body_str = event.get("body", "")
    if event.get("isBase64Encoded"):
        import base64
        body_str = base64.b64decode(body_str).decode("utf-8")

    # Parse form-encoded body (react-oauth2-code-pkce sends form-encoded)
    if "application/x-www-form-urlencoded" in content_type:
        params = dict(urllib.parse.parse_qsl(body_str))
    elif "application/json" in content_type:
        try:
            params = json.loads(body_str)
        except json.JSONDecodeError:
            return _response(400, {"error": "Invalid JSON body"})
    else:
        # Try form-encoded as default (the library sends this format)
        params = dict(urllib.parse.parse_qsl(body_str))

    # Validate required fields
    if "code" not in params or "code_verifier" not in params:
        return _response(400, {"error": "Missing required parameters: code, code_verifier"})

    # Allowlist: only forward safe OAuth parameters to Salesforce
    allowed_keys = {"grant_type", "code", "redirect_uri", "client_id", "code_verifier"}
    sf_params = {k: v for k, v in params.items() if k in allowed_keys}

    # Ensure grant_type is set
    sf_params.setdefault("grant_type", "authorization_code")

    # Forward to Salesforce token endpoint
    encoded_body = urllib.parse.urlencode(sf_params).encode("utf-8")

    req = urllib.request.Request(
        SF_TOKEN_URL,
        data=encoded_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            sf_body = resp.read().decode("utf-8")
            sf_status = resp.status
    except urllib.error.HTTPError as e:
        sf_body = e.read().decode("utf-8")
        sf_status = e.code
        logger.warning("Salesforce token endpoint returned %d: %s", sf_status, sf_body)
    except Exception:
        logger.exception("Failed to reach Salesforce token endpoint")
        return _response(502, {"error": "Failed to reach Salesforce token endpoint"})

    # Return Salesforce's response to the frontend (with CORS headers)
    try:
        sf_json = json.loads(sf_body)
    except json.JSONDecodeError:
        sf_json = {"raw": sf_body}

    return _response(sf_status, sf_json)
