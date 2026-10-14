"""
Shared Secrets Manager loader for MCP server Lambdas.

Reads a JSON-valued secret from AWS Secrets Manager and exposes individual
keys through os.environ for the rest of the Lambda to consume unchanged.
Falls back to existing env vars if the secret is unavailable (local dev).

Usage:
    from secrets_loader import hydrate_env_from_secret
    hydrate_env_from_secret("VENDOR_SECRET_NAME", required_keys=["FINNHUB_API_KEY"])

Why: keeps vendor API keys out of Lambda plaintext env vars and out of
samconfig.toml. Makes the repo reproducible — clone, populate one secret,
deploy, done. Runs once at Lambda cold start only (boto3 client reused).
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)


def hydrate_env_from_secret(
    env_var: str,
    *,
    required_keys: list[str] | None = None,
    default_secret_name: str | None = None,
) -> dict:
    """Read a JSON secret and merge its keys into os.environ.

    env_var             — env var holding the secret name (e.g. VENDOR_SECRET_NAME)
    required_keys       — raise if any of these are missing after hydration
    default_secret_name — fallback if env_var is unset

    Returns the parsed secret dict (for optional direct access).

    Never overwrites an env var that's already set — local dev (`TAVILY_API_KEY=...
    python app.py`) wins over Secrets Manager. This is what makes the same code
    work in Lambda and on a laptop.
    """
    secret_name = os.environ.get(env_var) or default_secret_name
    loaded: dict = {}

    if secret_name:
        try:
            import boto3  # imported lazily so unit tests don't need boto3

            client = boto3.client("secretsmanager")
            resp = client.get_secret_value(SecretId=secret_name)
            raw = resp.get("SecretString") or "{}"
            loaded = json.loads(raw)
            for key, val in loaded.items():
                if val and not os.environ.get(key):
                    os.environ[key] = str(val)
            logger.info(
                "Hydrated %d env vars from Secrets Manager (%s)",
                len(loaded), secret_name,
            )
        except Exception as exc:  # noqa: BLE001 — always continue, fall back to env
            logger.warning(
                "Could not load secret '%s': %s. Falling back to existing env vars.",
                secret_name, exc,
            )

    missing = [k for k in (required_keys or []) if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Missing required keys after secret hydration: {missing}. "
            f"Set them in Secrets Manager ({secret_name}) or export as env vars."
        )

    return loaded
