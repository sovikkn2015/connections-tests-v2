#!/bin/bash
# Run all Python module tests independently to avoid sys.modules collisions.
# Each module has its own models.py — running them in separate pytest processes
# prevents cross-module import pollution.

PASS=0
FAIL=0
TOTAL=0

run_tests() {
    local dir="$1"
    local name="$2"
    echo "──── $name ────"
    python3 -m pytest "$dir" -v --tb=short -q 2>&1
    local rc=$?
    if [ $rc -eq 0 ]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
    fi
    TOTAL=$((TOTAL + 1))
    echo ""
}

BASE="my-agent-project-007-fsi-interoperability/src"

# Core modules (Python)
run_tests "$BASE/m1-identity" "M1 Identity"
run_tests "$BASE/m2-m4-policy-engine" "M2/M4 Policy Engine"
run_tests "$BASE/m5-config-loader" "M5 Config Loader"
run_tests "$BASE/m6-mcp-gateway" "M6 MCP Gateway"
run_tests "$BASE/m8-pipeline-engine" "M8 Pipeline Engine"
run_tests "$BASE/m9-intent-router" "M9 Intent Router"
run_tests "$BASE/m10-audit-logger" "M10 Audit Logger"

# Specialist agents & services
run_tests "$BASE/smarsh-archiver" "Smarsh Archiver"
run_tests "$BASE/client-service-specialist" "Client Service Specialist"
run_tests "$BASE/memory-service" "Memory Service"

# Compliance sub-modules (run together — they use importlib isolation)
run_tests "$BASE/compliance" "Compliance (all 7 gaps)"

echo "════════════════════════════════════════"
echo "RESULTS: $PASS/$TOTAL passed, $FAIL failed"
echo "════════════════════════════════════════"

[ $FAIL -eq 0 ] && exit 0 || exit 1
