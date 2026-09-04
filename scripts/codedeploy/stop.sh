#!/bin/bash

APP_DIR="/opt/triage-assistant"

echo "==> Stopping existing application"

if [ ! -d "$APP_DIR" ]; then
    echo "==> Application directory does not exist. Nothing to stop."
    exit 0
fi

if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
    echo "==> docker-compose.yml does not exist. Nothing to stop."
    exit 0
fi

cd "$APP_DIR"

docker compose down || true

echo "==> Existing application stopped"
exit 0