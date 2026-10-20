#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="database/docker-compose.yml"

# 1. Stop JVM process if running
if [[ -f .backend.pid ]]; then
    PID=$(cat .backend.pid)
    echo "Stopping JVM (PID $PID)..."
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        sleep 2
        if kill -0 "$PID" 2>/dev/null; then
            kill -9 "$PID" 2>/dev/null || true
        fi
    fi
    rm -f .backend.pid
fi

# 2. Ensure port 8080 is released
fuser -k 8080/tcp > /dev/null 2>&1 || true

# 3. Stop database and remove all container volumes
echo "Stopping PostgreSQL and removing volumes..."
docker compose -f "$COMPOSE_FILE" down -v > /dev/null 2>&1

echo "Lab down."
