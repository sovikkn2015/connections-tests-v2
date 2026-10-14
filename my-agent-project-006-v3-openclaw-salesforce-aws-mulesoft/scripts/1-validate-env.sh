#!/usr/bin/env bash
# Validate local prerequisites for the V3 deploy. Fails fast with a clear
# message per missing tool or env var. Intended as the first script a
# fresh user runs.

set -e

need() {
    local cmd="$1"
    local min_version_msg="$2"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "[MISSING] $cmd (needed: $min_version_msg)"
        return 1
    fi
    echo "[ok]      $cmd -> $(command -v "$cmd")"
}

need aws "AWS CLI v2"
need sam "AWS SAM CLI >= 1.158"
need sf "Salesforce CLI (sf) >= 2.128"
need node "Node >= 20"
need npm "npm"
need python3 "Python >= 3.12 (for local builds)"
need mvn "Maven >= 3.9"
need java "JDK 17"
need jq "jq"
# Container runtime: finch or docker
if command -v finch >/dev/null 2>&1; then
    echo "[ok]      finch -> $(command -v finch)"
elif command -v docker >/dev/null 2>&1; then
    echo "[ok]      docker -> $(command -v docker)"
else
    echo "[MISSING] finch OR docker (needed for SAM build + AgentCore image)"
    exit 1
fi

# AWS identity
echo
echo "AWS caller identity:"
if ! aws sts get-caller-identity --output table 2>&1; then
    echo "[FAIL] AWS credentials not configured. Run: aws configure"
    exit 1
fi

# .env presence (gitignored)
echo
if [[ -f .env ]]; then
    echo "[ok]      .env present"
else
    echo "[WARN]    .env missing. Copy .env.example -> .env and fill in values."
fi

echo
echo "Environment validation complete."
