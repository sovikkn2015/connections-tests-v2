#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# test_dockerfile_security.sh
#
# Greps the four Wave 1 trust-layer Dockerfiles for forbidden patterns
# and required directives. Fails non-zero on any violation.
#
# Forbidden:
#   - `USER root` (case-insensitive, word-bounded)
#   - `ADD http(s)://` (ADD from URL is a supply-chain risk)
#   - `apt-get upgrade` (unpinned rolling upgrade)
#   - hardcoded credentials (PASSWORD=, TOKEN=<literal>, SECRET=)
#
# Required (at least one line matching each):
#   - `USER <numeric>` where <numeric> is UID 1000 (or another numeric UID)
#   - `HEALTHCHECK ` directive
#   - `org.opencontainers.image.title` LABEL
#
# Exit 0 on PASS, 1 on FAIL.
# -----------------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$HERE"

echo "[test_dockerfile_security] cwd=$(pwd)"

DOCKERFILES=(
  deploy/docker/m1-identity/Dockerfile
  deploy/docker/m2-m4-policy-engine/Dockerfile
  deploy/docker/m6-mcp-gateway/Dockerfile
  deploy/docker/m10-audit-logger/Dockerfile
  deploy/docker/m11-blpapi-adapter/Dockerfile
  deploy/docker/m11-grpc-adapter/Dockerfile
  deploy/docker/m13-fix-bridge/Dockerfile
)

FAILED=0

for df in "${DOCKERFILES[@]}"; do
  echo "---"
  echo "[test_dockerfile_security] scanning: $df"

  if [ ! -f "$df" ]; then
    echo "[test_dockerfile_security] FAIL -- file not found: $df"
    FAILED=1
    continue
  fi

  # ----- forbidden patterns -----
  if grep -En '^[[:space:]]*USER[[:space:]]+root([[:space:]]|$)' "$df" >/dev/null; then
    echo "[test_dockerfile_security] FAIL -- USER root present in $df"
    FAILED=1
  fi
  if grep -En '^[[:space:]]*ADD[[:space:]]+https?://' "$df" >/dev/null; then
    echo "[test_dockerfile_security] FAIL -- ADD from URL present in $df"
    FAILED=1
  fi
  if grep -En '^[[:space:]]*[^#][[:print:]]*apt-get[[:space:]]+upgrade' "$df" >/dev/null; then
    echo "[test_dockerfile_security] FAIL -- 'apt-get upgrade' (unpinned) present in $df"
    FAILED=1
  fi
  # Hardcoded credential heuristics.
  if grep -En '^[[:space:]]*ENV[[:space:]]+[A-Z_]*PASSWORD[[:space:]]*=?[[:space:]]*[A-Za-z0-9]+' "$df" >/dev/null; then
    echo "[test_dockerfile_security] FAIL -- hardcoded PASSWORD env in $df"
    FAILED=1
  fi
  if grep -En '^[[:space:]]*ENV[[:space:]]+[A-Z_]*SECRET[[:space:]]*=?[[:space:]]*[A-Za-z0-9]+' "$df" >/dev/null; then
    echo "[test_dockerfile_security] FAIL -- hardcoded SECRET env in $df"
    FAILED=1
  fi
  # `TOKEN_PATH=...` and similar are fine (they name a path, not a value).
  # Only fail if TOKEN= is followed by a literal >=16-char value.
  if grep -En '^[[:space:]]*ENV[[:space:]]+[A-Z_]*TOKEN[[:space:]]*=[[:space:]]*[A-Za-z0-9+/=]{16,}' "$df" >/dev/null; then
    echo "[test_dockerfile_security] FAIL -- hardcoded TOKEN env in $df"
    FAILED=1
  fi
  if grep -En 'BEGIN (RSA |EC )?PRIVATE KEY' "$df" >/dev/null; then
    echo "[test_dockerfile_security] FAIL -- PEM private key literal in $df"
    FAILED=1
  fi

  # ----- required directives -----
  if ! grep -En '^[[:space:]]*USER[[:space:]]+[0-9]+' "$df" >/dev/null; then
    echo "[test_dockerfile_security] FAIL -- no numeric USER directive in $df"
    FAILED=1
  fi
  if ! grep -En '^HEALTHCHECK' "$df" >/dev/null; then
    echo "[test_dockerfile_security] FAIL -- no HEALTHCHECK directive in $df"
    FAILED=1
  fi
  if ! grep -En 'org\.opencontainers\.image\.title' "$df" >/dev/null; then
    echo "[test_dockerfile_security] FAIL -- no org.opencontainers.image.title LABEL in $df"
    FAILED=1
  fi

  echo "[test_dockerfile_security] $df scanned"
done

echo "---"
if [ "$FAILED" -ne 0 ]; then
  echo "[test_dockerfile_security] RESULT: FAIL"
  exit 1
fi
echo "[test_dockerfile_security] RESULT: PASS"
exit 0
