"""
M8 Pipeline Engine -- AuditClient Protocol + implementations.

v0.2.0 NEW (Required Fix 4). Replaces v0.1.0's invented
``GatewayClient.emit_audit``. Talks directly to M10's FastAPI ``/audit``
endpoint over mTLS.

See `.kiro/specs/m8-pipeline-engine.md` R18, §Integration Point with M10.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable


class AuditEmitError(Exception):
    """Unified audit-emit failure type."""


@runtime_checkable
class AuditClient(Protocol):
    """Protocol for audit emission.

    M8 calls ``emit(entry)`` from every stage exactly once. M10 internally
    fans out to the 3-tier WORM (Langfuse + S3 Object Lock + CRM).
    """

    def emit(self, entry: dict) -> None:
        """POST entry to M10's /audit. Retry once on 5xx; second 5xx raises."""
        ...


class M10AuditClient:
    """Production AuditClient. mTLS HTTPS to M10 FastAPI."""

    def __init__(
        self,
        *,
        base_url: str,
        mtls_cert_path: str,
        timeout_ms: int = 10000,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/audit"
        self._cert = mtls_cert_path
        self._timeout = timeout_ms / 1000.0

    def emit(self, entry: dict) -> None:
        body = json.dumps(entry).encode("utf-8")
        for attempt in (1, 2):
            ctx = ssl.create_default_context()
            ctx.load_cert_chain(self._cert)
            req = urllib.request.Request(
                self._url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(
                    req, timeout=self._timeout, context=ctx
                ) as resp:
                    if 200 <= resp.status < 300:
                        return
                    if resp.status >= 500 and attempt == 1:
                        continue
                    raise AuditEmitError(f"status={resp.status}")
            except urllib.error.HTTPError as exc:
                if exc.code >= 500 and attempt == 1:
                    continue
                raise AuditEmitError(f"http_error={exc.code}")
            except urllib.error.URLError as exc:
                if attempt == 1:
                    continue
                raise AuditEmitError(f"url_error={exc!r}")
        raise AuditEmitError("retry_exhausted")


class FakeAuditClient:
    """Test AuditClient. Records every emit into ``.entries``."""

    def __init__(self, fail_at: int = -1) -> None:
        self.entries: list[dict] = []
        self._fail_at = fail_at
        self._count = 0

    def emit(self, entry: dict) -> None:
        self._count += 1
        if self._count == self._fail_at:
            raise AuditEmitError("fake_failure")
        self.entries.append(entry)


__all__ = [
    "AuditClient",
    "AuditEmitError",
    "M10AuditClient",
    "FakeAuditClient",
]
