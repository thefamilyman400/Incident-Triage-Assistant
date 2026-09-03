#!/bin/bash
set -e

APP_DIR="/opt/triage-assistant"

echo "Stopping existing application..."

if [ -f "$APP_DIR/docker-compose.yml" ]; then
    cd "$APP_DIR"
    docker compose down || true
fi

echo "Application stopped."