"""Anypoint Process API client — client-credentials OAuth.

Token obtained via OAuth2 client_credentials against the Anypoint
platform. Token cached until 60s before expiry. Retries 2x on 5xx
with exponential backoff.

Credential resolution order:
  1. Direct env vars: MULESOFT_CLIENT_ID / MULESOFT_CLIENT_SECRET
  2. SSM param names: MULESOFT_CLIENT_ID_PARAM / MULESOFT_CLIENT_SECRET_PARAM
     (resolved once at cold start via boto3 ssm:GetParameter)

This two-tier approach means:
  - `deploy-all.sh` can inject the actual values via env vars (fast path)
  - SAM template can set the SSM param names (no secrets in CloudFormation)
  - Either path works; direct env vars take precedence
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


MULESOFT_BASE_URL = os.environ.get("MULESOFT_BASE_URL", "https://anypoint.mulesoft.com")
MULESOFT_PROCESS_API_BASE = os.environ.get(
    "MULESOFT_PROCESS_API_BASE", "https://006-v3-trade-process-api.us-e2.cloudhub.io/api"
)


def _resolve_ssm(param_name: str) -> str:
    """Resolve an SSM SecureString parameter. Returns empty string on failure."""
    if not param_name:
        return ""
    try:
        import boto3
        ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        resp = ssm.get_parameter(Name=param_name, WithDecryption=True)
        return resp["Parameter"]["Value"]
    except Exception as exc:
        logger.warning("SSM resolve failed for %s: %s", param_name, exc)
        return ""


def _resolve_credential(direct_env: str, param_env: str) -> str:
    """Resolve a credential: direct env var first, then SSM param name."""
    val = os.environ.get(direct_env, "")
    if val:
        return val
    param_name = os.environ.get(param_env, "")
    if param_name:
        resolved = _resolve_ssm(param_name)
        if resolved:
            logger.info("Resolved %s from SSM param %s", direct_env, param_name)
            return resolved
    return ""


# Resolve once at cold start (Lambda keeps these across warm invocations)
MULESOFT_CLIENT_ID = _resolve_credential("MULESOFT_CLIENT_ID", "MULESOFT_CLIENT_ID_PARAM")
MULESOFT_CLIENT_SECRET = _resolve_credential("MULESOFT_CLIENT_SECRET", "MULESOFT_CLIENT_SECRET_PARAM")

_TOKEN: dict[str, Any] = {"value": None, "expires_at": 0.0}


def _get_token() -> str:
    now = time.time()
    if _TOKEN["value"] and _TOKEN["expires_at"] > now + 60:
        return _TOKEN["value"]

    if not MULESOFT_CLIENT_ID or not MULESOFT_CLIENT_SECRET:
        raise RuntimeError("MULESOFT_CLIENT_ID/SECRET not configured")

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{MULESOFT_BASE_URL}/accounts/api/v2/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": MULESOFT_CLIENT_ID,
                    "client_secret": MULESOFT_CLIENT_SECRET,
                },
            )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Anypoint token network error: {exc}") from exc

    if not resp.is_success:
        raise RuntimeError(f"Anypoint token exchange failed: {resp.status_code} {resp.text[:200]}")
    body = resp.json()
    _TOKEN["value"] = body["access_token"]
    _TOKEN["expires_at"] = now + int(body.get("expires_in", 3600))
    return _TOKEN["value"]


class MulesoftClient:
    """Thin client for Anypoint Process APIs."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or MULESOFT_PROCESS_API_BASE).rstrip("/")

    def _headers(self, principal_id: str) -> dict:
        return {
            "Authorization": f"Bearer {_get_token()}",
            "Content-Type": "application/json",
            "X-Principal-Id": principal_id,
        }

    def call(self, method: str, endpoint: str, json_body: dict, principal_id: str) -> dict:
        url = f"{self.base_url}{endpoint}"
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.request(method, url, headers=self._headers(principal_id), json=json_body)
            except httpx.HTTPError as exc:
                last_exc = exc
                time.sleep(0.2 * (2**attempt))
                continue

            if 200 <= resp.status_code < 300:
                return resp.json() if resp.content else {}

            if resp.status_code >= 500 and attempt < 2:
                time.sleep(0.3 * (2**attempt))
                continue

            raise RuntimeError(
                f"Anypoint {method} {endpoint} failed: {resp.status_code} {resp.text[:200]}"
            )

        raise RuntimeError(f"Anypoint {method} {endpoint} all retries failed: {last_exc}")
