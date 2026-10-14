"""
Smarsh Archiver — Service for FINRA Rule 17a-4 communication archiving.

SHA-256 hash of content before archiving for integrity verification.
In-memory store for dev/test. REST API call to Smarsh in production (injected client).
No cross-module imports. No credentials in code.
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from .models import ArchiveRecord, ArchiveResult, ContentType, SmarshConfig
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _models_path = _pathlib.Path(__file__).parent / "models.py"
    _spec = importlib.util.spec_from_file_location("smarsh_models_local", _models_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ArchiveRecord = _mod.ArchiveRecord
    ArchiveResult = _mod.ArchiveResult
    ContentType = _mod.ContentType
    SmarshConfig = _mod.SmarshConfig

logger = logging.getLogger("smarsh_archiver.archiver")


class SmarshArchiver:
    """
    Smarsh archiving service for BD communications.

    Production: REST API calls to Smarsh via injected httpx client.
    Dev/test: in-memory store.
    """

    def __init__(
        self,
        config: Optional[SmarshConfig] = None,
        http_client: Optional[Any] = None,
    ) -> None:
        self._config = config or SmarshConfig(firm_id="dev-firm")
        self._client = http_client  # httpx.AsyncClient for production (injected)
        self._store: dict[str, ArchiveRecord] = {}  # in-memory for dev/test

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """Compute SHA-256 hash of content for integrity verification."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def archive_communication(
        self,
        content: str,
        content_type: str | ContentType,
        metadata: Optional[dict] = None,
    ) -> ArchiveResult:
        """
        Archive a communication to Smarsh.

        Types: agent_response, meeting_summary, research_brief, trade_confirmation.
        SHA-256 hash computed before archiving for integrity.
        """
        try:
            if isinstance(content_type, str):
                content_type = ContentType(content_type)
        except ValueError:
            return ArchiveResult(
                success=False,
                error=f"Invalid content_type: {content_type}. "
                       f"Valid: {[ct.value for ct in ContentType]}",
            )

        content_hash = self.compute_content_hash(content)
        record_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        try:
            receipt_id: Optional[str] = None

            if self._client is not None:
                # Production: POST to Smarsh REST API
                payload = {
                    "firm_id": self._config.firm_id,
                    "content": content,
                    "content_type": content_type.value,
                    "content_hash": content_hash,
                    "metadata": metadata or {},
                    "timestamp": now,
                }
                resp = await self._client.post(
                    self._config.api_endpoint,
                    json=payload,
                )
                resp.raise_for_status()
                receipt_id = resp.json().get("receipt_id", str(uuid.uuid4()))
            else:
                # Dev/test: in-memory
                receipt_id = f"SMARSH-{uuid.uuid4().hex[:12].upper()}"

            record = ArchiveRecord(
                record_id=record_id,
                content_hash=content_hash,
                content_type=content_type,
                archived_at=now,
                retention_years=6,
                smarsh_receipt_id=receipt_id,
                firm_id=self._config.firm_id,
                metadata=metadata,
            )
            self._store[record_id] = record

            logger.info(
                "Archived %s: record=%s receipt=%s hash=%s",
                content_type.value, record_id, receipt_id, content_hash[:16],
            )
            return ArchiveResult(
                success=True, receipt_id=receipt_id, record_id=record_id,
            )

        except Exception as exc:
            logger.error("Archive failed: %s", exc)
            return ArchiveResult(success=False, error=str(exc))

    async def verify_archive(self, receipt_id: str) -> bool:
        """
        Verify a record exists in Smarsh by receipt ID.
        Production: GET to Smarsh API. Dev/test: check in-memory store.
        """
        if self._client is not None:
            try:
                resp = await self._client.get(
                    f"{self._config.api_endpoint}/verify/{receipt_id}",
                )
                return resp.status_code == 200
            except Exception as exc:
                logger.error("Verify failed: %s", exc)
                return False

        # Dev/test: check in-memory store
        return any(
            r.smarsh_receipt_id == receipt_id for r in self._store.values()
        )

    async def get_archive_status(self, record_id: str) -> Optional[ArchiveRecord]:
        """
        Get archive record by internal record ID.
        Returns None if not found.
        """
        if self._client is not None:
            try:
                resp = await self._client.get(
                    f"{self._config.api_endpoint}/status/{record_id}",
                )
                if resp.status_code == 200:
                    return ArchiveRecord(**resp.json())
                return None
            except Exception as exc:
                logger.error("Get status failed: %s", exc)
                return None

        return self._store.get(record_id)
