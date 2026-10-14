"""SF Auth Proxy Lambda — per-principal OAuth On-Behalf-Of.

The salesforce-crm MCP Lambda calls THIS Lambda internally to obtain a
short-lived Salesforce access_token scoped to a specific user.

Why this exists (V3 Auth Boundary 4): the CRM MCP does NOT use a long-
lived service account token — that would flatten all users into one
identity and break FSC sharing rules.

OAuth flow: JWT Bearer grant. The Connected App's certificate private
key lives in Secrets Manager (`/006-v3/sf/bootstrap-creds`). In mock
mode this Lambda returns a deterministic token.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SF_LOGIN_URL = os.environ.get("SF_LOGIN_URL", "https://login.salesforce.com")
SF_BOOTSTRAP_SECRET = os.environ.get("SF_BOOTSTRAP_SECRET", "/006-v3/sf/bootstrap-creds")
SF_AUTH_PROXY_KEY = os.environ.get("SF_AUTH_PROXY_KEY", "")
MOCK_MODE = os.environ.get("SF_AUTH_PROXY_MODE", "live").lower() == "mock"

_BOOTSTRAP_CACHE: dict[str, Any] = {}


def _load_bootstrap() -> dict:
    if _BOOTSTRAP_CACHE:
        return _BOOTSTRAP_CACHE
    if MOCK_MODE:
        _BOOTSTRAP_CACHE.update(
            {
                "client_id": "MOCK_CLIENT_ID",
                "subject_pattern": "{principal_email}",
                "audience": SF_LOGIN_URL,
                "private_key_pem": "",
            }
        )
        return _BOOTSTRAP_CACHE
    try:
        import boto3
        sm = boto3.client("secretsmanager")
        resp = sm.get_secret_value(SecretId=SF_BOOTSTRAP_SECRET)
        _BOOTSTRAP_CACHE.update(json.loads(resp["SecretString"]))
        return _BOOTSTRAP_CACHE
    except Exception as exc:
        logger.exception("Failed to load SF bootstrap secret")
        raise RuntimeError(f"Bootstrap secret load failed: {exc}") from exc


def _mint_jwt(principal_id: str) -> str:
    creds = _load_bootstrap()
    if MOCK_MODE or not creds.get("private_key_pem"):
        return f"MOCK-JWT-{principal_id[:20]}"
    try:
        import jwt
    except ImportError as exc:
        raise RuntimeError(f"PyJWT not installed: {exc}") from exc

    now = int(time.time())
    claims = {
        "iss": creds["client_id"],
        "sub": creds["subject_pattern"].format(principal_email=principal_id),
        "aud": creds["audience"],
        "exp": now + 180,
    }
    return jwt.encode(claims, creds["private_key_pem"], algorithm="RS256")


def _exchange_jwt(jwt_str: str) -> dict:
    if MOCK_MODE:
        return {
            "access_token": f"MOCK-ACCESS-{jwt_str[-12:]}",
            "instance_url": "https://mock.my.salesforce.com",
            "expires_in": 3600,
        }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{SF_LOGIN_URL}/services/oauth2/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": jwt_str,
                },
            )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"SF token exchange network error: {exc}") from exc

    if not resp.is_success:
        raise RuntimeError(f"SF token exchange failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event: dict, context: Any = None) -> dict:
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    dev_mode = os.environ.get("MCP_DEV_MODE", "").lower() == "true"
    if not SF_AUTH_PROXY_KEY:
        # Fail-closed: missing SF_AUTH_PROXY_KEY is a misconfig, not an open
        # door. Only explicit dev mode allows unauthenticated calls.
        if not dev_mode:
            return _response(
                500,
                {
                    "error": "misconfigured",
                    "message": (
                        "SF_AUTH_PROXY_KEY env var required; "
                        "set MCP_DEV_MODE=true only for local dev"
                    ),
                },
            )
    elif headers.get("x-internal-auth") != SF_AUTH_PROXY_KEY:
        return _response(401, {"error": "unauthorized"})

    if (event.get("httpMethod") or "POST").upper() != "POST":
        return _response(405, {"error": "method not allowed"})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid json"})

    principal_id = body.get("principal_id")
    if not isinstance(principal_id, str) or not principal_id:
        return _response(400, {"error": "principal_id required"})

    try:
        jwt_str = _mint_jwt(principal_id)
        token_body = _exchange_jwt(jwt_str)
    except Exception as exc:
        logger.exception("OBO failed for %s", principal_id)
        return _response(502, {"error": f"OBO failed: {exc}"})

    return _response(200, token_body)
