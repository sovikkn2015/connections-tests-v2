"""
M9 Task 2 -- Hardcoded credential scan.

AC14.1: no literal assignments matching credential shapes.
"""

from __future__ import annotations

import pathlib
import re

SRC_ROOT = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src"
    / "m9_intent_router"
)

_CRED_PAT = re.compile(
    r"(?i)(api_key|apikey|secret|password|access_key|aws_access_key_id|"
    r"aws_secret_access_key)\s*=\s*['\"][^'\"]+['\"]"
)


def test_no_hardcoded_creds_in_src():
    for py in SRC_ROOT.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        content = py.read_text()
        matches = _CRED_PAT.findall(content)
        assert not matches, (
            f"{py.name} contains credential-shaped assignment: {matches}"
        )


def test_env_example_no_credential_keys():
    """AC14.4 -- .env.example uses vault path templates, no literal secrets."""
    env = SRC_ROOT / ".env.example"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, _ = line.partition("=")
            key_l = key.lower()
            for banned in (
                "api_key",
                "apikey",
                "password",
                "access_key",
                "secret",
            ):
                # banned keys allowed only when the key is a vault PATH.
                if banned in key_l and "vault" not in key_l and "path" not in key_l:
                    raise AssertionError(
                        f".env.example has credential-shaped key: {key}"
                    )
