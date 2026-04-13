#!/bin/sh
# wait-for-http.sh — Poll an HTTP endpoint until it returns the expected status or timeout.
#
# Usage:
#   wait-for-http.sh --host HOST --port PORT [options]
#
# Options:
#   --host HOST             Hostname or IP (required)
#   --port PORT             Port number (required)
#   --path PATH             URL path to check (default: /)
#   --timeout SECONDS       Max wait time in seconds (default: 60)
#   --interval SECONDS      Time between retries in seconds (default: 2)
#   --expected-status CODE  Expected HTTP status code (default: 200)
#
# Exit codes:
#   0  Service became ready (returned expected status)
#   1  Timed out waiting for service
#
# Example:
#   ./wait-for-http.sh --host localhost --port 8000 --timeout 30 --path /health

set -e

# Defaults
HOST=""
PORT=""
PATH_VAR="/"
TIMEOUT=60
INTERVAL=2
EXPECTED_STATUS=200

# Parse arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --host)
            HOST="$2"; shift 2 ;;
        --port)
            PORT="$2"; shift 2 ;;
        --path)
            PATH_VAR="$2"; shift 2 ;;
        --timeout)
            TIMEOUT="$2"; shift 2 ;;
        --interval)
            INTERVAL="$2"; shift 2 ;;
        --expected-status)
            EXPECTED_STATUS="$2"; shift 2 ;;
        *)
            echo "Error: Unknown option $1" >&2; exit 1 ;;
    esac
done

# Validate required arguments
if [ -z "$HOST" ] || [ -z "$PORT" ]; then
    echo "Error: --host and --port are required" >&2
    exit 1
fi

URL="http://${HOST}:${PORT}${PATH_VAR}"
ELAPSED=0

echo "Waiting for ${URL} (status ${EXPECTED_STATUS}, timeout ${TIMEOUT}s)..."

while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${URL}" 2>/dev/null || true)

    if [ "$HTTP_STATUS" = "$EXPECTED_STATUS" ]; then
        echo "Service ready: ${URL} returned ${HTTP_STATUS} (${ELAPSED}s elapsed)"
        exit 0
    fi

    sleep "$INTERVAL"
    ELAPSED=$((ELAPSED + INTERVAL))
done

echo "Timeout after ${TIMEOUT}s waiting for ${URL} (last status: ${HTTP_STATUS})" >&2
exit 1
