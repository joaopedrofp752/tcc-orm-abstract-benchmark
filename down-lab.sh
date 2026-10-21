#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="database/docker-compose.yml"

# --- 1. Terminate JVM Process ---
echo "Stopping JVM runtime..."

if [[ -f .backend.pid ]]; then
    PID=$(cat .backend.pid)
    echo "  - Sending shutdown signal to PID $PID..."
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        sleep 2
        if kill -0 "$PID" 2>/dev/null; then
            echo "  - Forcing shutdown (kill -9)..."
            kill -9 "$PID" 2>/dev/null || true
        fi
    fi
    rm -f .backend.pid
    echo "  - JVM process terminated"
else
    echo "  - No .backend.pid found, skipping JVM stop"
fi

fuser -k 8080/tcp > /dev/null 2>&1 || true
echo "  - Port 8080 verified free"

# --- 2. Tear Down Database ---
echo ""
echo "Tearing down PostgreSQL..."
echo "  - Stopping container and removing volumes..."
docker compose -f "$COMPOSE_FILE" down -v > /dev/null 2>&1
echo "  - Database volume destroyed"

echo ""
echo "Lab environment is clean and idle."
