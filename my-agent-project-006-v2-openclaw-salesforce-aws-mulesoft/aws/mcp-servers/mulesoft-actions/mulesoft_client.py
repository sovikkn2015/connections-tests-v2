"""MuleSoft Anypoint API client.

Reads OAuth credentials from AWS Secrets Manager (never from env vars or files).
Fetches and caches access tokens. Handles 401 auto-refresh.

Environment:
    MULESOFT_SECRET_NAME  AWS Secrets Manager secret name (e.g. /006-v2/mulesoft/credentials)
    AWS_REGION            Region where the secret lives (Lambda provides this automatically)

The secret JSON shape:
    {
        "client_id":       "...",
        "client_secret":   "...",
        "base_url":        "https://anypoint.mulesoft.com" or "https://eu1.anypoint.mulesoft.com",
        "organization_id": "uuid",
        "environment_id":  "uuid"
    }
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import boto3
import urllib.request
import urllib.parse
import urllib.error


_SECRET_NAME_ENV = "MULESOFT_SECRET_NAME"
_DEFAULT_SECRET_NAME = "/006-v2/mulesoft/credentials"

_TOKEN_REFRESH_BUFFER_SECONDS = 300  # refresh 5 min before actual expiry


@dataclass
class _CachedToken:
    access_token: str
    expires_at_epoch: int  # unix timestamp when token becomes invalid


class MuleSoftClientError(Exception):
    """Raised when MuleSoft API calls fail."""


class MuleSoftAuthError(MuleSoftClientError):
    """Raised when OAuth token cannot be obtained."""


class MuleSoftClient:
    """Thin wrapper around MuleSoft Anypoint Platform REST APIs.

    Read-only for Phase 6 scaffolding. Action-taking methods (submit_order,
    initiate_wire, etc.) are layered on top in the skill, not here.
    """

    def __init__(self, secret_name: str | None = None) -> None:
        self._secret_name = secret_name or os.environ.get(_SECRET_NAME_ENV, _DEFAULT_SECRET_NAME)
        self._secrets_client = boto3.client("secretsmanager")
        self._creds: dict[str, str] | None = None
        self._cached_token: _CachedToken | None = None

    # -- Credentials -----------------------------------------------------

    def _load_credentials(self) -> dict[str, str]:
        if self._creds is not None:
            return self._creds

        try:
            response = self._secrets_client.get_secret_value(SecretId=self._secret_name)
        except Exception as exc:
            raise MuleSoftAuthError(f"Failed to read secret '{self._secret_name}': {exc}") from exc

        secret_string = response.get("SecretString")
        if not secret_string:
            raise MuleSoftAuthError(f"Secret '{self._secret_name}' has no SecretString value")

        try:
            creds = json.loads(secret_string)
        except json.JSONDecodeError as exc:
            raise MuleSoftAuthError(f"Secret '{self._secret_name}' is not valid JSON: {exc}") from exc

        required = {"client_id", "client_secret", "base_url", "organization_id", "environment_id"}
        missing = required - set(creds.keys())
        if missing:
            raise MuleSoftAuthError(f"Secret missing required keys: {missing}")

        self._creds = creds
        return creds

    # -- OAuth -----------------------------------------------------------

    def _fetch_token(self) -> _CachedToken:
        creds = self._load_credentials()
        base_url = creds["base_url"].rstrip("/")
        token_url = f"{base_url}/accounts/api/v2/oauth2/token"

        form_body = urllib.parse.urlencode({
            "grant_type": "client_credentials",
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
        }).encode()

        request = urllib.request.Request(
            token_url,
            data=form_body,
            method="POST",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode() if hasattr(exc, "read") else str(exc)
            raise MuleSoftAuthError(f"Token fetch failed: HTTP {exc.code} - {detail[:200]}") from exc
        except urllib.error.URLError as exc:
            raise MuleSoftAuthError(f"Token fetch network error: {exc}") from exc

        try:
            payload = json.loads(body)
        except json.JSONDecodeError as exc:
            raise MuleSoftAuthError(f"Token response was not JSON: {body[:200]}") from exc

        access_token = payload.get("access_token")
        expires_in = payload.get("expires_in", 0)
        if not access_token:
            raise MuleSoftAuthError(f"Token response missing access_token: {payload}")

        return _CachedToken(
            access_token=access_token,
            expires_at_epoch=int(time.time()) + int(expires_in) - _TOKEN_REFRESH_BUFFER_SECONDS,
        )

    def get_access_token(self) -> str:
        """Return a cached token if still valid, otherwise fetch a fresh one."""
        now = int(time.time())
        if self._cached_token is not None and now < self._cached_token.expires_at_epoch:
            return self._cached_token.access_token
        self._cached_token = self._fetch_token()
        return self._cached_token.access_token

    # -- Generic authenticated HTTP --------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        query: dict[str, str] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Issue an authenticated request to MuleSoft Anypoint. Auto-refresh token on 401."""
        creds = self._load_credentials()
        base_url = creds["base_url"].rstrip("/")
        url = f"{base_url}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        body_bytes = json.dumps(json_body).encode() if json_body is not None else None

        def _do(access_token: str) -> tuple[int, dict[str, Any]]:
            req = urllib.request.Request(
                url,
                data=body_bytes,
                method=method.upper(),
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    **({"Content-Type": "application/json"} if body_bytes is not None else {}),
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode() or "{}"
                    return resp.status, json.loads(raw)
            except urllib.error.HTTPError as exc:
                err_raw = exc.read().decode() if hasattr(exc, "read") else ""
                try:
                    err_payload = json.loads(err_raw) if err_raw else {}
                except json.JSONDecodeError:
                    err_payload = {"raw": err_raw}
                return exc.code, err_payload

        token = self.get_access_token()
        status, body = _do(token)

        if status == 401:
            # Stale or revoked token: clear cache and retry once.
            self._cached_token = None
            token = self.get_access_token()
            status, body = _do(token)

        if status >= 400:
            raise MuleSoftClientError(f"MuleSoft {method} {path} -> HTTP {status}: {body}")

        return body

    # -- Process API calls (CloudHub-deployed endpoints) ----------------

    def request_process_api(
        self,
        method: str,
        full_url: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Issue an authenticated request against a CloudHub-deployed Process API.

        Uses the same bearer token as the Anypoint platform OAuth flow. The URL is
        passed in full (e.g. https://{app}.{region}.cloudhub.io/api/orders) because
        it does not share the `base_url` prefix used for platform calls.
        """
        body_bytes = json.dumps(json_body).encode() if json_body is not None else None

        def _do(access_token: str) -> tuple[int, dict[str, Any]]:
            req = urllib.request.Request(
                full_url,
                data=body_bytes,
                method=method.upper(),
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    **({"Content-Type": "application/json"} if body_bytes is not None else {}),
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode() or "{}"
                    return resp.status, json.loads(raw)
            except urllib.error.HTTPError as exc:
                err_raw = exc.read().decode() if hasattr(exc, "read") else ""
                try:
                    err_payload = json.loads(err_raw) if err_raw else {}
                except json.JSONDecodeError:
                    err_payload = {"raw": err_raw}
                return exc.code, err_payload

        token = self.get_access_token()
        status, body = _do(token)

        if status == 401:
            self._cached_token = None
            token = self.get_access_token()
            status, body = _do(token)

        if status >= 400:
            raise MuleSoftClientError(f"Process API {method} {full_url} -> HTTP {status}: {body}")

        return body

    def get_credential(self, key: str) -> str | None:
        """Return a single value from the credentials secret (or None if missing).

        Used by the Lambda to read optional config like `process_api_base_url`
        without forcing it into the required-keys list.
        """
        creds = self._load_credentials()
        value = creds.get(key)
        return value if value else None

    # -- Convenience wrappers (add more as process APIs come online) ------

    def who_am_i(self) -> dict[str, Any]:
        """Return info about the authenticated Connected App. Smoke test for sandbox mode."""
        return self.request("GET", "/accounts/api/me")

    def list_environments(self) -> dict[str, Any]:
        """List environments in the current org. Requires the Environment Admin scope."""
        creds = self._load_credentials()
        org_id = creds["organization_id"]
        return self.request("GET", f"/accounts/api/organizations/{org_id}/environments")
