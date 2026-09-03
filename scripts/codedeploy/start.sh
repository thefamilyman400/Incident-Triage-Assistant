#!/bin/bash
set -e

APP_DIR="/opt/triage-assistant"

echo "Starting application..."

cd "$APP_DIR"

docker compose up -d

echo "Application started."