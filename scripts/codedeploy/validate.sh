#!/bin/bash
set -euo pipefail

echo "==> Validating Incident Triage Assistant"

for i in {1..30}; do

    if curl -sf http://localhost:8080/health; then
        echo ""
        echo "================================"
        echo "Application is healthy!"
        echo "================================"
        exit 0
    fi

    echo "Health check attempt $i/30 failed."
    sleep 5

done

echo "Application failed health check."

cd /opt/triage-assistant

docker compose ps
docker compose logs --tail=100

exit 1