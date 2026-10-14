"""
M10 Audit Logger -- FastAPI legal-hold endpoint unit tests.

Wave 4 deliverable. Spec: .kiro/specs/m10-legal-hold-api.md §3 Task 6.

Covers the three legal-hold routes on ``src/m10_audit_logger/app.py``:
* POST   /audit/legal-hold
* DELETE /audit/legal-hold
* GET    /audit/legal-hold/{canonical_id}

Auth enforcement (compliance_officer role via M1 verify_aid), body
validation, error mapping, empty-list response.

Run:
    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest my-agent-project-007-fsi-interoperability/\\
            tests/unit/test_m10_app_legal_hold.py -v
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from m10_audit_logger.app import create_app
from m10_audit_logger.backends_minio.legal_hold import (
    HoldEntry,
    LegalHoldError,
)


# =============================================================================
# Fakes
# =============================================================================


class FakeBackend:
    """Minimal MinIOWormBackend stand-in covering the 3 legal-hold methods."""

    def __init__(
        self,
        *,
        place_raises: Optional[LegalHoldError] = None,
        release_raises: Optional[LegalHoldError] = None,
        list_raises: Optional[LegalHoldError] = None,
    ) -> None:
        self.place_raises = place_raises
        self.release_raises = release_raises
        self.list_raises = list_raises
        self.place_calls: list[dict] = []
        self.release_calls: list[dict] = []
        self.list_calls: list = []
        self._active: dict[tuple, HoldEntry] = {}

    def place_legal_hold(
        self, *, canonical_id, hold_id, reason, placed_by
    ) -> HoldEntry:
        self.place_calls.append(
            {
                "canonical_id": canonical_id,
                "hold_id": hold_id,
                "reason": reason,
                "placed_by": placed_by,
            }
        )
        if self.place_raises is not None:
            raise self.place_raises
        entry = HoldEntry(
            hold_id=hold_id,
            canonical_id=canonical_id,
            reason=reason,
            placed_by=placed_by,
            placed_at=datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        )
        self._active[(canonical_id, hold_id)] = entry
        return entry

    def release_legal_hold(
        self, *, canonical_id, hold_id, reason, released_by
    ) -> HoldEntry:
        self.release_calls.append(
            {
                "canonical_id": canonical_id,
                "hold_id": hold_id,
                "reason": reason,
                "released_by": released_by,
            }
        )
        if self.release_raises is not None:
            raise self.release_raises
        active = self._active.get((canonical_id, hold_id))
        if active is None:
            raise LegalHoldError("hold_not_found")
        released = HoldEntry(
            hold_id=active.hold_id,
            canonical_id=active.canonical_id,
            reason=reason,
            placed_by=active.placed_by,
            placed_at=active.placed_at,
            released_at=datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
            released_by=released_by,
        )
        self._active.pop((canonical_id, hold_id))
        return released

    def list_legal_holds(self, canonical_id) -> list[HoldEntry]:
        self.list_calls.append(canonical_id)
        if self.list_raises is not None:
            raise self.list_raises
        return [
            e for (cid, _hid), e in self._active.items() if cid == canonical_id
        ]


def _verify_aid_compliance_officer(token: str) -> dict:
    # Ignore the token value -- tests drive the assertion via role claims.
    return {
        "sub": "urn:007:m1:aid:compliance-officer-1",
        "roles": ["compliance_officer"],
    }


def _verify_aid_advisor_only(token: str) -> dict:
    return {"sub": "urn:007:m1:aid:advisor-1", "roles": ["advisor"]}


def _make_client(
    *,
    backend: Optional[FakeBackend] = None,
    verify_aid=_verify_aid_compliance_officer,
) -> tuple[TestClient, FakeBackend]:
    """Shared client factory."""
    app = create_app()
    app.state.minio_worm_backend = backend if backend is not None else FakeBackend()
    app.state.verify_aid = verify_aid
    return TestClient(app), app.state.minio_worm_backend


_SHA256_64 = "a" * 64
_BEARER = {"Authorization": "Bearer test-jwt"}


# =============================================================================
# Tests
# =============================================================================


class TestPlaceHold:

    # --- Case 1 ---
    def test_post_happy_path_returns_202(self):
        client, backend = _make_client()
        cid = uuid4()
        resp = client.post(
            "/audit/legal-hold",
            json={
                "canonical_id": str(cid),
                "hold_id": "matter-A",
                "reason": "SEC subpoena SDNY-2026-0001",
                "placed_by": _SHA256_64,
            },
            headers=_BEARER,
        )
        assert resp.status_code == 202
        payload = resp.json()
        assert payload["status"] == "placed"
        assert payload["hold_id"] == "matter-A"
        # ISO-8601 UTC with Z suffix.
        assert payload["placed_at"].endswith("Z")
        # Backend was called with the parsed UUID.
        assert backend.place_calls[0]["canonical_id"] == cid

    # --- Case 2 ---
    def test_post_without_authorization_returns_403(self):
        client, _ = _make_client()
        cid = uuid4()
        resp = client.post(
            "/audit/legal-hold",
            json={
                "canonical_id": str(cid),
                "hold_id": "matter-B",
                "reason": "x" * 10,
                "placed_by": _SHA256_64,
            },
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "missing_token"

    # --- Case 3 ---
    def test_post_with_non_compliance_role_returns_403(self):
        client, _ = _make_client(verify_aid=_verify_aid_advisor_only)
        cid = uuid4()
        resp = client.post(
            "/audit/legal-hold",
            json={
                "canonical_id": str(cid),
                "hold_id": "matter-C",
                "reason": "attempting without role",
                "placed_by": _SHA256_64,
            },
            headers=_BEARER,
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "role_required"

    # --- Case 4 ---
    def test_post_duplicate_hold_id_returns_409(self):
        client, _ = _make_client(
            backend=FakeBackend(
                place_raises=LegalHoldError("duplicate_hold_id")
            )
        )
        cid = uuid4()
        resp = client.post(
            "/audit/legal-hold",
            json={
                "canonical_id": str(cid),
                "hold_id": "dup",
                "reason": "dup attempt",
                "placed_by": _SHA256_64,
            },
            headers=_BEARER,
        )
        assert resp.status_code == 409
        assert resp.json()["error"] == "duplicate_hold_id"

    # --- Case 5 ---
    def test_post_missing_required_key_returns_400(self):
        client, _ = _make_client()
        # omit `placed_by`
        resp = client.post(
            "/audit/legal-hold",
            json={
                "canonical_id": str(uuid4()),
                "hold_id": "matter-D",
                "reason": "missing field",
            },
            headers=_BEARER,
        )
        assert resp.status_code == 400
        payload = resp.json()
        assert payload["error"] == "missing_required_keys"
        assert payload["missing"] == ["placed_by"]


class TestReleaseHold:

    # --- Case 6 ---
    def test_delete_happy_path_returns_200(self):
        backend = FakeBackend()
        client, _ = _make_client(backend=backend)
        cid = uuid4()
        # Seed an active hold
        client.post(
            "/audit/legal-hold",
            json={
                "canonical_id": str(cid),
                "hold_id": "to-be-released",
                "reason": "placed first",
                "placed_by": _SHA256_64,
            },
            headers=_BEARER,
        )
        resp = client.request(
            "DELETE",
            "/audit/legal-hold",
            json={
                "canonical_id": str(cid),
                "hold_id": "to-be-released",
                "reason": "matter closed",
                "released_by": _SHA256_64,
            },
            headers=_BEARER,
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "released"
        assert payload["hold_id"] == "to-be-released"
        assert payload["released_at"].endswith("Z")

    # --- Case 7 ---
    def test_delete_wrong_hold_id_returns_404(self):
        backend = FakeBackend()
        client, _ = _make_client(backend=backend)
        cid = uuid4()
        resp = client.request(
            "DELETE",
            "/audit/legal-hold",
            json={
                "canonical_id": str(cid),
                "hold_id": "never-placed",
                "reason": "releasing a nonexistent hold",
                "released_by": _SHA256_64,
            },
            headers=_BEARER,
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "hold_not_found"


class TestListHolds:

    # --- Case 8a ---
    def test_get_returns_list_of_active_holds(self):
        backend = FakeBackend()
        client, _ = _make_client(backend=backend)
        cid = uuid4()
        client.post(
            "/audit/legal-hold",
            json={
                "canonical_id": str(cid),
                "hold_id": "active-1",
                "reason": "first",
                "placed_by": _SHA256_64,
            },
            headers=_BEARER,
        )
        resp = client.get(
            f"/audit/legal-hold/{cid}",
            headers=_BEARER,
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["canonical_id"] == str(cid)
        assert len(payload["holds"]) == 1
        assert payload["holds"][0]["hold_id"] == "active-1"
        assert payload["holds"][0]["is_active"] is True

    # --- Case 8b ---
    def test_get_returns_empty_list_when_no_holds(self):
        client, _ = _make_client(backend=FakeBackend())
        cid = uuid4()
        resp = client.get(
            f"/audit/legal-hold/{cid}",
            headers=_BEARER,
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["holds"] == []

    def test_get_without_auth_returns_403(self):
        client, _ = _make_client(backend=FakeBackend())
        cid = uuid4()
        resp = client.get(f"/audit/legal-hold/{cid}")
        assert resp.status_code == 403
