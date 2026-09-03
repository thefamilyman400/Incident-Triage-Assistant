#!/bin/bash
set -euo pipefail

APP_DIR="/opt/triage-assistant"

echo "==> Deploying Incident Triage Assistant"

cd "$APP_DIR"

if [ ! -f image-definition.env ]; then
    echo "ERROR: image-definition.env not found"
    exit 1
fi

source image-definition.env

if [ -z "${ECR_IMAGE:-}" ]; then
    echo "ERROR: ECR_IMAGE is empty"
    exit 1
fi

echo "==> Deploying image:"
echo "$ECR_IMAGE"

AWS_REGION="${AWS_REGION:-ap-south-1}"

echo "==> Logging in to ECR"

ECR_REGISTRY="$(echo "$ECR_IMAGE" | cut -d/ -f1)"

aws ecr get-login-password --region "$AWS_REGION" \
    | docker login \
        --username AWS \
        --password-stdin "$ECR_REGISTRY"

echo "==> Pulling image"

docker pull "$ECR_IMAGE"

echo "==> Starting application"

export ECR_IMAGE

docker compose up -d

echo "==> Deployment complete"