#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/database/docker-compose.yml"
PID_FILE="$ROOT_DIR/.backend.pid"
DB_PID_FILE="$ROOT_DIR/.database_log.pid"

BACKEND_LOG="$ROOT_DIR/backend.log"
DB_LOG="$ROOT_DIR/database.log"

# 1. Environment Pre-flight
echo "Checking environment..."

if ! docker info > /dev/null 2>&1; then
    echo "  ! Error: Docker daemon is not running."
    exit 1
fi
echo "  - Docker daemon is active"

if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "  ! Error: Compose file not found at '$COMPOSE_FILE'."
    exit 1
fi

if ss -tuln | grep -q ':5432 '; then
    echo "  ! Error: Port 5432 is already occupied."
    exit 1
fi

if ss -tuln | grep -q ':8080 '; then
    echo "  ! Error: Port 8080 is already occupied."
    exit 1
fi
echo "  - Ports 5432 and 8080 are free"

# 2. Database Initialization & Telemetry
echo ""
echo "Initializing PostgreSQL..."
echo "  - Starting container via Docker Compose..."
docker compose -f "$COMPOSE_FILE" up -d > /dev/null 2>&1

echo "[$(date +'%Y-%m-%d %H:%M:%S')] PostgreSQL Container Initialized" >> "$DB_LOG"
docker compose -f "$COMPOSE_FILE" logs -f db >> "$DB_LOG" 2>&1 &
echo $! > "$DB_PID_FILE"
echo "  - Database logging attached -> $(basename "$DB_LOG")"

DB_TIMEOUT=90
DB_ELAPSED=0

until docker compose -f "$COMPOSE_FILE" exec -T db pg_isready -U postgres > /dev/null 2>&1; do
    printf "\r  - Waiting for database readiness: %ds / %ds..." "$DB_ELAPSED" "$DB_TIMEOUT"
    sleep 1
    DB_ELAPSED=$((DB_ELAPSED + 1))
    if [[ $DB_ELAPSED -ge $DB_TIMEOUT ]]; then
        echo ""
        echo "  ! Error: Database readiness timed out after ${DB_TIMEOUT}s."
        echo "  ! Hint: Check $(basename "$DB_LOG") for details."
        exit 1
    fi
done
printf "\r  - PostgreSQL is accepting connections (ready in %ds)             \n" "$DB_ELAPSED"

# 3. Backend Build
echo ""
echo "Compiling backend..."
echo "  - Running Maven clean package..."
if ! (cd "$ROOT_DIR/backend" && ./mvnw clean package -DskipTests -q); then
    echo "  ! Error: Maven build failed."
    exit 1
fi

JAR_FILE=$(ls "$ROOT_DIR"/backend/target/*.jar 2>/dev/null | grep -v 'original' | head -n 1 || true)
if [[ -z "$JAR_FILE" ]]; then
    echo "  ! Error: Executable JAR not found in backend/target/."
    exit 1
fi
echo "  - Artifact ready: $(basename "$JAR_FILE")"

# 4. JVM Startup & Health Check
echo ""
echo "Launching JVM..."
echo "  - Configuration: -Xms1g -Xmx1g -XX:+UseG1GC"
echo "[$(date +'%Y-%m-%d %H:%M:%S')] JVM Backend Initialized" >> "$BACKEND_LOG"
java -XX:+UseG1GC -Xms1g -Xmx1g -jar "$JAR_FILE" >> "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$PID_FILE"
echo "  - Process started (PID $BACKEND_PID) -> $(basename "$BACKEND_LOG")"

APP_TIMEOUT=60
APP_ELAPSED=0

until curl -s -f http://localhost:8080/actuator/health | grep -q '"status":"UP"'; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo ""
        echo "  ! Error: Backend process exited prematurely."
        echo "  ! Hint: Check $(basename "$BACKEND_LOG") for details."
        exit 1
    fi

    printf "\r  - Waiting for Actuator health check: %ds / %ds..." "$APP_ELAPSED" "$APP_TIMEOUT"
    sleep 1
    APP_ELAPSED=$((APP_ELAPSED + 1))
    if [[ $APP_ELAPSED -ge $APP_TIMEOUT ]]; then
        echo ""
        echo "  ! Error: Health check timed out after ${APP_TIMEOUT}s."
        echo "  ! Hint: Check $(basename "$BACKEND_LOG") for details."
        exit 1
    fi
done
printf "\r  - Health check UP (:8080/actuator/health in %ds)                  \n" "$APP_ELAPSED"

echo ""
echo "Lab environment is ready (PID $BACKEND_PID)."
