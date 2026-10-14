"""
M9 Intent Router -- Tenant-scoped HMAC-SHA-256 utterance digest (Fix 10).

Prevents cross-tenant rainbow-table attack on short/predictable utterances.
Tenant key is resolved from Vault / AWS Secrets Manager once per process and
cached in memory via functools.lru_cache.

See `.kiro/specs/m9-intent-router.md` R8 AC8.1 + R14 AC14.7.
"""

from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache


@lru_cache(maxsize=128)
def _resolve_tenant_hmac_key(tenant_id: str, vault_path: str) -> bytes:
    """Fetch tenant HMAC key from Vault / Secrets Manager. Cached per process.

    Vault path template (recommended):
    ``secret/data/m9/tenants/<tenant_id>/hmac_key``.

    The literal ``<tenant_id>`` substring is replaced with the caller-supplied
    ``tenant_id`` before fetching. Fail-closed on empty bytes.

    Phase 2 uses AWS Secrets Manager. Phase 3+ may swap to HashiCorp Vault SDK
    behind the same function signature (single-seam migration per AC14.7).

    Raises RuntimeError("provider_unconfigured") if the secret is empty/absent
    -- pod fails readiness, Kubernetes crash-loops until config is fixed.
    """
    import boto3  # AC13.3 -- boto3 allowed in hmac_util.py ONLY (Vault adapter).

    sm = boto3.client("secretsmanager")
    path = vault_path.replace("<tenant_id>", tenant_id)
    resp = sm.get_secret_value(SecretId=path)
    raw = resp.get("SecretBinary") or (resp.get("SecretString") or "").encode(
        "utf-8"
    )
    if not raw:
        raise RuntimeError("provider_unconfigured")  # fail-closed
    return raw


def compute_utterance_digest(utterance: str, tenant_key: bytes) -> str:
    """Return 64-char hex HMAC-SHA-256 digest (AC8.1).

    Single migration seam for future SHA-3 / BLAKE3 per Known Blockers row 13.
    """
    return hmac.new(
        tenant_key, utterance.encode("utf-8"), hashlib.sha256
    ).hexdigest()
