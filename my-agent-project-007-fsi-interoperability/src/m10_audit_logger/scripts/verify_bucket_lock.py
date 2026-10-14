"""
M10 Audit Logger -- bucket-policy probe (initContainer).

Runs at pod boot, BEFORE the main M10 container starts. Exits with
a non-zero status code when any of the following is true:

1. The configured MinIO endpoint is unreachable.
2. The configured bucket does not exist.
3. Object Lock is not enabled on the bucket.
4. Object Lock mode on the bucket does not match the configured
   mode (COMPLIANCE or GOVERNANCE).

Fail-closed per Steering Rule 8: no "proceed and warn" branch. The
pod never reaches Ready if the bucket configuration is wrong.

Config is supplied as a single YAML file path via ``sys.argv[1]``
(matching the MinIOWormConfig field set). Vault-backed credentials
are mounted at ``/vault/secrets/minio-access`` and
``/vault/secrets/minio-secret`` by the Vault Agent Sidecar. The
script does NOT read process-environment variables -- the M10 source
tree is deliberately free of ``process-env lookup functions`` so the
security grep stays authoritative.

Exit codes:
    0 -- bucket is OK.
    1 -- bucket is misconfigured; pod must not start.
    2 -- configuration error (missing/unreadable config file or
         Vault secret). Pod must not start.

Run at pod boot (from values-cloud.yaml):
    python -m m10_audit_logger.scripts.verify_bucket_lock \\
        /etc/m10/minio-config.yaml
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import yaml


class _StartupVaultClient:
    """Reads Vault-injected secret files from the sidecar mount path."""

    def __init__(self, root: str = "/vault/secrets"):
        self._root = Path(root)

    def read_secret(self, path: str) -> str:
        if path.endswith("access_key"):
            return (self._root / "minio-access").read_text().strip()
        if path.endswith("secret_key"):
            return (self._root / "minio-secret").read_text().strip()
        raise KeyError(path)


def _load_config(path: Path):
    from m5_config_loader import MinIOWormConfig

    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(
            f"config file {path} must be a YAML mapping at the "
            "top level"
        )
    return MinIOWormConfig.model_validate(data)


def main(argv: Optional[list[str]] = None) -> int:
    from m10_audit_logger import AuditWriteError
    from m10_audit_logger.backends_minio.minio_worm import MinIOWormBackend

    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        sys.stderr.write(
            "[verify_bucket_lock] usage: verify_bucket_lock "
            "<minio-config.yaml>\n"
        )
        return 2

    cfg_path = Path(args[0])
    if not cfg_path.is_file():
        sys.stderr.write(
            f"[verify_bucket_lock] config file not found: {cfg_path}\n"
        )
        return 2

    try:
        cfg = _load_config(cfg_path)
    except Exception as exc:
        sys.stderr.write(
            f"[verify_bucket_lock] invalid config: {type(exc).__name__}\n"
        )
        return 2

    try:
        vault = _StartupVaultClient()
        # Constructing the backend runs the health check.
        MinIOWormBackend(config=cfg, vault_client=vault)
    except AuditWriteError as exc:
        sys.stderr.write(
            f"[verify_bucket_lock] FAIL-CLOSED: reason={exc.reason}\n"
        )
        return 1
    except Exception as exc:
        sys.stderr.write(
            f"[verify_bucket_lock] startup error: "
            f"{type(exc).__name__}\n"
        )
        return 1

    sys.stdout.write(
        "[verify_bucket_lock] OK: bucket configured, Object Lock mode "
        f"matches ({cfg.object_lock_mode}).\n"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover -- initContainer entrypoint
    sys.exit(main())
