"""
M1 Identity — Uvicorn entrypoint for containerized deployment.

Generates an ephemeral RSA key pair for local dev if M1_PRIVATE_KEY_PEM
and M1_PUBLIC_KEY_PEM are not set. Production MUST provide real keys
via Vault/Secrets Manager (Rule 20).
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app import create_app


def _generate_dev_keys() -> tuple[str, str]:
    """Generate ephemeral RSA-2048 key pair for local dev only."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


_priv = os.environ.get("M1_PRIVATE_KEY_PEM", "")
_pub = os.environ.get("M1_PUBLIC_KEY_PEM", "")

if not _priv or not _pub:
    _priv, _pub = _generate_dev_keys()

app = create_app(private_key=_priv, public_key=_pub)
