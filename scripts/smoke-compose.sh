#!/bin/bash
# smoke-compose.sh — Validate all 5 services are healthy after docker compose up.
#
# Checks:
#   1. PostgreSQL  (port from POSTGRES_PORT env, default 18432)
#   2. Redis       (port from REDIS_PORT env, default 18379)
#   3. Main Server (port from MAIN_SERVER_PORT env, default 18000)
#   4. Orthanc     (port from ORTHANC_HTTP_PORT env, default 18042)
#   5. BIDS Server (port from BIDS_SERVER_PORT env, default 18080)
#
# Usage:
#   ./scripts/smoke-compose.sh              # start docker compose, then check
#   ./scripts/smoke-compose.sh --skip-startup  # check without starting

set -euo pipefail

SKIP_STARTUP=false
for arg in "$@"; do
    case "$arg" in
        --skip-startup) SKIP_STARTUP=true ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Read port configuration from environment with defaults matching docker-compose.yml
POSTGRES_PORT="${POSTGRES_PORT:-18432}"
REDIS_PORT="${REDIS_PORT:-18379}"
MAIN_SERVER_PORT="${MAIN_SERVER_PORT:-18000}"
ORTHANC_HTTP_PORT="${ORTHANC_HTTP_PORT:-18042}"
BIDS_SERVER_PORT="${BIDS_SERVER_PORT:-18080}"

PASS=0
FAIL=0

# ---- start containers ----
if [ "$SKIP_STARTUP" = false ]; then
    echo "==> Starting docker compose services..."
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" up -d --build --quiet-pull
    echo "    Containers started. Waiting 5s for init..."
    sleep 5
fi

# ---- helper: record pass / fail ----
check_result() {
    local name="$1" ok="$2"
    if [ "$ok" = true ]; then
        echo "    [PASS] $name"
        PASS=$((PASS + 1))
    else
        echo "    [FAIL] $name"
        FAIL=$((FAIL + 1))
    fi
}

echo ""
echo "============================================"
echo "  VNA Stack Smoke Test"
echo "============================================"
echo ""

# 1. PostgreSQL
echo "--> Checking PostgreSQL (port ${POSTGRES_PORT})..."
if pg_isready -h localhost -p "${POSTGRES_PORT}" -U vna -d postgres -q 2>/dev/null; then
    check_result "PostgreSQL" true
else
    check_result "PostgreSQL" false
fi

# 2. Redis
echo "--> Checking Redis (port ${REDIS_PORT})..."
if docker compose -f "$PROJECT_ROOT/docker-compose.yml" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
    check_result "Redis" true
elif redis-cli -h localhost -p "${REDIS_PORT}" ping 2>/dev/null | grep -q PONG; then
    check_result "Redis" true
else
    check_result "Redis" false
fi

# 3. Main Server
echo "--> Checking Main Server (port ${MAIN_SERVER_PORT})..."
if "$SCRIPT_DIR/wait-for-http.sh" --host localhost --port "${MAIN_SERVER_PORT}" --path /v1/health --timeout 60 --interval 2 --expected-status 200 2>/dev/null; then
    check_result "Main Server (${MAIN_SERVER_PORT})" true
else
    check_result "Main Server (${MAIN_SERVER_PORT})" false
fi

# 4. Orthanc
echo "--> Checking Orthanc (port ${ORTHANC_HTTP_PORT})..."
if "$SCRIPT_DIR/wait-for-http.sh" --host localhost --port "${ORTHANC_HTTP_PORT}" --path /system --timeout 60 --interval 3 --expected-status 200 2>/dev/null; then
    check_result "Orthanc (${ORTHANC_HTTP_PORT})" true
else
    check_result "Orthanc (${ORTHANC_HTTP_PORT})" false
fi

# 5. BIDS Server
echo "--> Checking BIDS Server (port ${BIDS_SERVER_PORT})..."
if "$SCRIPT_DIR/wait-for-http.sh" --host localhost --port "${BIDS_SERVER_PORT}" --path /health --timeout 60 --interval 2 --expected-status 200 2>/dev/null; then
    check_result "BIDS Server (${BIDS_SERVER_PORT})" true
else
    check_result "BIDS Server (${BIDS_SERVER_PORT})" false
fi

# ---- summary ----
echo ""
echo "============================================"
echo "  Results: $PASS passed, $FAIL failed"
echo "============================================"

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
exit 0
