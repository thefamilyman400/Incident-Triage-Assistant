# ── Stage 1: build dependencies ────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools needed for numpy / sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY app/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime image ──────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/

# Copy knowledge base directories only when NOT using S3.
# If S3_BUCKET_NAME is set at runtime the app loads docs from S3 instead.
# These local copies serve as a fallback / local-dev default.
COPY runbooks/ ./runbooks/
COPY incidents/ ./incidents/
COPY docs/ ./docs/

# Pre-download the sentence-transformers model so it's baked into the image
# (avoids a 90MB download on every cold start)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Persistent vector store lives in a volume so it survives redeploys
VOLUME ["/app/app/vector_store"]

# FastAPI via uvicorn
EXPOSE 8080

# Health check — Lightsail/ECS will use this
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Add app/ to PYTHONPATH so `from vector_store import ...` and `from aws import ...`
# resolve correctly when uvicorn imports app.main as a package
ENV PYTHONPATH="/app/app"

# Run from /app so relative paths (runbooks/, incidents/, docs/) resolve correctly
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
