#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="database/docker-compose.yml"

# 1. Start PostgreSQL container
echo "Starting PostgreSQL..."
docker compose -f "$COMPOSE_FILE" up -d > /dev/null 2>&1

# 2. Wait until PostgreSQL is accepting connections
until docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    sleep 1
done

# 3. Build backend JAR
echo "Building backend..."
(cd backend && ./mvnw clean package -DskipTests -q)

JAR_FILE=$(ls backend/target/*.jar | grep -v 'original' | head -n 1)

# 4. Launch JVM with fixed memory allocation and G1GC
echo "Starting JVM..."
java -XX:+UseG1GC -Xms2g -Xmx2g -jar "$JAR_FILE" > backend.log 2>&1 &
echo $! > .backend.pid

# 5. Wait for Spring Boot Actuator health check
until curl -s -f http://localhost:8080/actuator/health | grep -q '"status":"UP"'; do
    if ! kill -0 "$(<.backend.pid)" 2>/dev/null; then
        echo "Error: backend failed to start. Check backend.log"
        exit 1
    fi
    sleep 1
done

echo "Lab ready (PID $(cat .backend.pid))."
