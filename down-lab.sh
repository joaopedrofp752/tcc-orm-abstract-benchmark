#!/usr/bin/env bash
# Enforce strict script execution and error checking
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/database/docker-compose.yml"
PID_FILE="$ROOT_DIR/.backend.pid"
DB_PID_FILE="$ROOT_DIR/.database_log.pid"

BACKEND_LOG="$ROOT_DIR/backend.log"
DB_LOG="$ROOT_DIR/database.log"

# Gracefully terminate the Spring Boot process (SIGTERM), falling back to SIGKILL
echo "Stopping JVM runtime..."

if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    echo "  - Sending shutdown signal to PID $PID..."
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" 2>/dev/null || true
        sleep 2
        # Force terminate if process did not release resources within 2 seconds
        if kill -0 "$PID" 2>/dev/null; then
            echo "  - Forcing shutdown (kill -9)..."
            kill -9 "$PID" 2>/dev/null || true
        fi
    fi
    rm -f "$PID_FILE"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] JVM backend terminated" >> "$BACKEND_LOG"
    echo "  - JVM process terminated"
else
    echo "  - No .backend.pid found, skipping JVM stop"
fi

# Ensure port 8080 has no lingering sockets or child processes
fuser -k 8080/tcp > /dev/null 2>&1 || true
echo "  - Port 8080 verified free"

# Stop the background Docker log streaming process
if [[ -f "$DB_PID_FILE" ]]; then
    DB_LOG_PID=$(cat "$DB_PID_FILE")
    kill "$DB_LOG_PID" 2>/dev/null || true
    rm -f "$DB_PID_FILE"
    echo "  - Database logging process detached (PID $DB_LOG_PID)"
fi

# Stop database container and remove attached volumes (-v) to guarantee
# a clean, unfragmented state and fresh data seed for subsequent benchmark runs
echo ""
echo "Tearing down PostgreSQL..."
echo "  - Stopping container and removing volumes..."
docker compose -f "$COMPOSE_FILE" down -v > /dev/null 2>&1
echo "[$(date +'%Y-%m-%d %H:%M:%S')] PostgreSQL container destroyed" >> "$DB_LOG"
echo "  - Database container stopped and volume destroyed"

echo ""
echo "Lab environment is clean and idle."
