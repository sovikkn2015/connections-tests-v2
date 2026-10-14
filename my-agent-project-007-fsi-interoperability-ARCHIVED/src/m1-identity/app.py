"""
M1 FastAPI application — Agent Identity Service REST endpoints.

Endpoints:
    POST /aid/issue    — Issue a new AID (returns signed JWT)
    POST /aid/verify   — Verify an AID token (called by M6 on every request)
    POST /aid/revoke   — Revoke an AID (immediate effect)
    GET  /health       — Health check

No cross-module imports. M6 calls these endpoints via REST.
"""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException

try:
    from .aid_service import AIDService, AIDRegistry, KeyProvider
    from .models import (
        IssueAIDRequest,
        IssueAIDResponse,
        VerifyAIDRequest,
        VerifyAIDResponse,
        RevokeAIDRequest,
        RevokeAIDResponse,
    )
except ImportError:
    from aid_service import AIDService, AIDRegistry, KeyProvider
    from models import (
        IssueAIDRequest,
        IssueAIDResponse,
        VerifyAIDRequest,
        VerifyAIDResponse,
        RevokeAIDRequest,
        RevokeAIDResponse,
    )

logger = logging.getLogger("m1.app")


# ── App factory ──────────────────────────────────────────────────


def create_app(
    private_key: str | None = None,
    public_key: str | None = None,
) -> FastAPI:
    """
    Create the M1 FastAPI application.

    Keys can be provided directly (tests) or via environment variables:
        M1_PRIVATE_KEY_PEM — RSA private key (PEM format)
        M1_PUBLIC_KEY_PEM  — RSA public key (PEM format)

    Production: keys loaded from KMS/Vault at startup (Rule 9).
    Dev/test: generated locally or from env vars.
    """
    _private_key = private_key or os.environ.get("M1_PRIVATE_KEY_PEM", "")
    _public_key = public_key or os.environ.get("M1_PUBLIC_KEY_PEM", "")

    if not _private_key or not _public_key:
        raise RuntimeError(
            "M1 requires RSA key pair. Set M1_PRIVATE_KEY_PEM and "
            "M1_PUBLIC_KEY_PEM environment variables, or pass keys "
            "to create_app()."
        )

    key_provider = KeyProvider(_private_key, _public_key)
    registry = AIDRegistry()
    service = AIDService(key_provider, registry)

    app = FastAPI(
        title="M1 Agent Identity Service",
        description=(
            "Issues, verifies, and revokes Agent Identity Documents (AIDs). "
            "JWT RS256 with FSI-specific claims."
        ),
        version="0.1.0",
    )

    # Store service on app state for endpoint access
    app.state.aid_service = service

    @app.get("/health")
    async def health():
        return {"status": "ok", "module": "m1-identity", "version": "0.1.0"}

    @app.post("/aid/issue", response_model=IssueAIDResponse)
    async def issue_aid(request: IssueAIDRequest):
        """Issue a new Agent Identity Document."""
        try:
            return app.state.aid_service.issue(request)
        except Exception as e:
            logger.error("AID issuance failed: %s", e)
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/aid/verify", response_model=VerifyAIDResponse)
    async def verify_aid(request: VerifyAIDRequest):
        """
        Verify an AID token. Called by M6 on every request.

        Returns valid=True with claims, or valid=False with reason.
        Never throws — always returns a VerifyAIDResponse.
        """
        return app.state.aid_service.verify(request.token)

    @app.post("/aid/revoke", response_model=RevokeAIDResponse)
    async def revoke_aid(request: RevokeAIDRequest):
        """Revoke an AID. Immediate effect."""
        try:
            return app.state.aid_service.revoke(
                request, revoked_by="system"
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return app
