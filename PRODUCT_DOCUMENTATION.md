# Infrastructure Incident Triage Assistant
### Product Documentation v3.0

**Project:** IBM WatsonX Challenge — Use Case 2
**Stack:** FastAPI · Google Gemini 2.5 Flash · Sentence Transformers · NumPy · AWS S3 · Secrets Manager
**Deployment:** Docker · GitHub Actions · AWS EC2 (t3.small)
**Last Updated:** 2025-07-28

---

## Table of Contents

1. [Product Overview](#1-product-overview)
2. [Problem Statement](#2-problem-statement)
3. [Solution Summary](#3-solution-summary)
4. [Architecture](#4-architecture)
5. [Technology Stack](#5-technology-stack)
6. [Backend](#6-backend)
7. [Frontend](#7-frontend)
8. [RAG Pipeline](#8-rag-pipeline)
9. [Vector Index](#9-vector-index)
10. [AWS Integrations](#10-aws-integrations)
11. [Knowledge Base](#11-knowledge-base)
12. [API Reference](#12-api-reference)
13. [Features](#13-features)
14. [File Structure](#14-file-structure)
15. [Setup & Run](#15-setup--run)
16. [Deployment](#16-deployment)
17. [Known Limitations & Future Work](#17-known-limitations--future-work)

---

## 1. Product Overview

The **Infrastructure Incident Triage Assistant** is a RAG-powered AI assistant for on-call infrastructure engineers. It eliminates the 30–60 minute context-gathering phase that precedes every production incident by instantly surfacing the relevant runbook, past incident history, diagnostic commands, and escalation guidance — all grounded in your actual operational documentation.

### Key Value Proposition

| Before | After |
|---|---|
| Search Confluence for runbooks (15–20 min) | Exact runbook retrieved in < 2 seconds |
| Check Slack for past incidents (10–15 min) | Similar incidents surfaced with root cause instantly |
| Figure out escalation path (5–10 min) | Exact escalation path from policy, cited |
| **Total: 30–45 min before diagnosis starts** | **Total: < 30 seconds** |

---

## 2. Problem Statement

When an alert fires at 2 AM, on-call engineers face three immediate challenges:

1. **Context gap** — No immediate knowledge of which runbook applies or whether it has happened before
2. **Documentation scatter** — Runbooks in Confluence, incidents in Jira, contacts in PagerDuty — all separate logins
3. **Knowledge silos** — Resolution knowledge lives in the heads of senior engineers who are not always available

These challenges directly inflate **MTTR (Mean Time to Resolution)** — a universally understood infrastructure KPI.

---

## 3. Solution Summary

A web application hosted on AWS EC2 that:

- Loads infrastructure documentation from **AWS S3** (runbooks, post-mortems, policies) at startup
- Pulls API keys securely from **AWS Secrets Manager**
- Builds a persistent local vector index — loads from disk in < 200ms on subsequent starts
- Accepts natural language queries from the engineer
- Retrieves the top 6 most semantically relevant document chunks
- Injects retrieved chunks + conversation history into a structured prompt sent to **Google Gemini 2.5 Flash**
- Falls back automatically to **Groq (Llama 3.1)** when Gemini is unavailable or rate-limited
- Streams the response word-by-word via Server-Sent Events
- Detects incident severity (P1–P4) automatically from the alert description
- Generates IaC remediation templates (Terraform, Ansible, K8s, shell, Prometheus)
- Generates complete runbook `.md` documents from resolved triage conversations
- Generates branching investigation + remediation workflows
- Allows new documents to be uploaded to S3 and re-indexed without restarting

---

## 4. Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Engineer's Browser                        │
│              http://EC2_IP:8080                              │
│             (index.html — Single Page App)                   │
└───────────────────┬─────────────────────────────────────────┘
                    │ HTTP POST /query/stream  (SSE)
                    │ HTTP POST /query, /report, /generate/*
                    ▼
┌─────────────────────────────────────────────────────────────┐
│           Docker Container — FastAPI (main.py)              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                    RAG Pipeline                      │    │
│  │  1. Severity detection (keyword)                     │    │
│  │  2. Embed query (all-MiniLM-L6-v2, local)           │    │
│  │  3. Cosine similarity search (NumPy, < 5ms)          │    │
│  │  4. Retrieve top-6 chunks                            │    │
│  │  5. Build prompt: system + history + context         │    │
│  │  6. Stream Gemini 2.5 Flash response via SSE         │    │
│  │     └─ Auto-fallback to Groq on any Gemini error     │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Persistent Vector Index                    │    │
│  │  vector_store/chunks.json + embeddings.npy           │    │
│  │  Fingerprint includes S3 backend — stale on switch   │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌─────────────┐  ┌──────────────────────────────┐
│ Gemini 2.5  │  │         AWS                  │
│ Flash API   │  │  S3 — document storage       │
│ (primary)   │  │  Secrets Manager — API keys  │
└─────────────┘  └──────────────────────────────┘
       │
       ▼ (on failure)
┌─────────────┐
│ Groq API    │
│ (fallback)  │
└─────────────┘
```

### Startup Sequence

```
Server starts
     │
     ├─ load_dotenv() — read .env
     ├─ get_api_keys() — overlay with Secrets Manager (if configured)
     ├─ Initialise Gemini 2.5 Flash client
     ├─ Initialise Groq client (if GROQ_API_KEY set)
     ├─ Load all-MiniLM-L6-v2 embedding model
     ├─ s3_load_documents() — load from S3 if S3_BUCKET_NAME set
     │   └─ fallback: load from local runbooks/ incidents/ docs/
     ├─ Check fingerprint (includes backend: s3:bucket or local)
     │   ├─ MATCH  → load index from disk (< 200ms)
     │   └─ STALE  → re-embed → save to disk (~60s first time)
     └─ FastAPI server ready
```

---

## 5. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **LLM (primary)** | Google Gemini 2.5 Flash | Latest | Response generation (streaming) |
| **LLM (fallback)** | Groq / Llama 3.1 8B | Latest | Auto-fallback on Gemini errors |
| **Embeddings** | sentence-transformers / all-MiniLM-L6-v2 | 3.0.1 | Local vector embedding |
| **Vector Search** | NumPy cosine similarity + JSON | 1.26.4 | Nearest-neighbour search + persistence |
| **Backend** | FastAPI | 0.111.0 | REST API + SSE streaming |
| **ASGI Server** | Uvicorn | 0.30.1 | HTTP server |
| **Frontend** | Vanilla HTML/CSS/JS | — | Single page app, no build step |
| **Document Storage** | AWS S3 (optional) | — | Cloud document storage |
| **Secrets** | AWS Secrets Manager (optional) | — | Secure API key storage |
| **AWS SDK** | boto3 | ≥1.34.0 | S3 + Secrets Manager client |
| **Container** | Docker + Docker Compose | — | Containerised deployment |
| **CI/CD** | GitHub Actions | — | Auto-deploy to EC2 on push to main |
| **Hosting** | AWS EC2 t3.small | — | 2 vCPU, 2GB RAM, Ubuntu 22.04 |
| **Language** | Python | 3.12 | Backend runtime |

---

## 6. Backend

**Files:** `app/main.py`, `app/vector_store.py`, `app/aws.py`

### main.py — Responsibilities

```
main.py
├── Config loading — .env + Secrets Manager overlay (aws.py)
├── Gemini 2.5 Flash client init
├── Groq fallback client init (optional)
├── Embedding model loading (SentenceTransformer)
├── Document loading — S3 or local (aws.py)
├── Document chunking
├── Index building — persistent via vector_store.py
├── Vector search
├── Severity detection
├── Prompt construction — system + context + history
├── LLM error handling — (ResourceExhausted, GoogleAPIError) → Groq fallback
└── FastAPI routes:
    GET  /               → serve index.html
    GET  /health         → index stats + model + backend
    POST /query          → standard triage
    POST /query/stream   → SSE streaming triage
    POST /report         → incident post-mortem
    POST /generate/iac   → IaC remediation templates
    POST /generate/runbook → runbook generation
    POST /orchestrate    → branching investigation workflow
    POST /upload         → upload to S3/disk + re-index (folder selector)
    POST /reindex        → force full re-index
    POST /embed          → shared embedding endpoint for other apps
    GET  /documents      → list indexed documents
```

### aws.py — AWS Integration Layer

```
aws.py
├── load_secrets()           → fetch JSON secret from Secrets Manager
├── get_api_keys()           → Secrets Manager first, .env fallback
├── s3_load_documents()      → list + download all .md/.txt from S3 bucket
├── s3_upload_document()     → upload a file to S3 under a folder prefix
└── s3_list_document_keys()  → list all S3 keys in knowledge base
```

Both integrations are **opt-in via env vars** — if not configured, the app behaves exactly as before.

### vector_store.py — Persistence Layer

```
vector_store.py
├── save_index()          → write chunks.json + embeddings.npy
├── load_index()          → read from disk (< 200ms)
├── is_index_current()    → MD5 fingerprint check (includes S3 backend prefix)
└── cosine_search()       → top-k cosine similarity
```

The fingerprint includes the S3 backend identifier (`s3:bucket-name` or `local`) — switching from local to S3 always triggers a full rebuild.

### LLM Fallback Strategy

Every endpoint catches both `ResourceExhausted` and `GoogleAPIError`:

```
Gemini call
  ├─ Success → return response
  └─ (ResourceExhausted OR GoogleAPIError)
       ├─ groq_client set → call Groq → return response
       └─ no groq_client → return friendly error message
```

This means deprecated models, quota exhaustion, network errors, and rate limits all fall through to Groq automatically.

---

## 7. Frontend

**File:** `app/static/index.html` — self-contained, no npm, no build step.

### Key UI Components

| Component | Description |
|---|---|
| **Streaming toggle** | Header checkbox — SSE streaming vs standard request |
| **Severity banner** | Red P1 / Orange P2 / Blue P3 / Grey P4 per response |
| **Response time badge** | Green < 3s, yellow 3–8s, orange > 8s |
| **Code blocks** | Syntax-highlighted with hover Copy button |
| **Source chips** | Cited document filenames at bottom of each response |
| **Generate Report** | Post-mortem modal from any response |
| **Generate IaC** | IaC remediation templates modal |
| **Generate Runbook** | Save resolved conversation as a new runbook |
| **Orchestrate** | Branching investigation workflow modal |
| **Folder selector** | Dropdown on upload: `runbooks/` · `incidents/` · `docs/` |
| **Upload zone** | Drag-and-drop or click — live re-index status shown |
| **Quick prompts** | Pre-built chips for common queries |
| **Welcome scenarios** | Four alert scenario cards — click to auto-submit |
| **Chat history panel** | Past sessions grouped Today / Earlier — click to replay |
| **Similar sessions** | Related past sessions surfaced after each response |

---

## 8. RAG Pipeline

```
INGEST (startup)
  S3 or local .md files
  → Split into 500-char overlapping chunks (100-char overlap)
  → Embed each chunk with all-MiniLM-L6-v2 (batch size 16)
  → Save chunks.json + embeddings.npy to disk
  → Subsequent starts: load from disk in < 200ms

RETRIEVE (per query)
  Embed query → 384-dim vector
  → Cosine similarity vs all chunk vectors (< 5ms)
  → Return top-6 chunks by score

AUGMENT (per query)
  SYSTEM_PROMPT + top-6 chunks (with source + score) + last 3 exchanges + query

GENERATE (per query)
  Stream to Gemini 2.5 Flash → SSE tokens → markdown rendered in real-time
  On any Gemini error → auto-fallback to Groq
```

### Retrieval Parameters

| Parameter | Value | Rationale |
|---|---|---|
| `TOP_K` | 6 | Runbook + incidents + policy without bloating context |
| `CHUNK_SIZE` | 500 chars | ~3–5 runbook steps per chunk |
| `CHUNK_OVERLAP` | 100 chars | Prevents boundary splits |
| `EMBED_BATCH_SIZE` | 16 | Reduced from 32 to lower peak memory on 2GB instances |
| History window | 6 messages | Last 3 exchanges |

---

## 9. Vector Index

| Metric | Value |
|---|---|
| Total documents | 13 (+ uploads) |
| Total chunks | ~399 |
| Embedding dimensions | 384 |
| Vector array on disk | ~0.6 MB |
| Index build time (first run) | ~60s |
| Index load time (subsequent) | < 200ms |
| Query retrieval time | < 5ms |

Fingerprint logic ensures the index rebuilds automatically when:
- Documents are added or removed
- The backend switches between local and S3

---

## 10. AWS Integrations

### S3 — Document Storage

Documents are loaded from S3 at startup if `S3_BUCKET_NAME` is set. The bucket structure mirrors the local folder layout:

```
s3://your-bucket/
  runbooks/HIGH_CPU_RUNBOOK.md
  incidents/INC-2847-HIGH-CPU-BATCH-JOB.md
  docs/ESCALATION_POLICY.md
```

Upload via UI → writes to S3 under the selected folder prefix.
Seed the bucket from local files: `python scripts/s3_sync.py`

### Secrets Manager

If `SECRETS_MANAGER_ARN` is set, API keys are fetched from Secrets Manager at startup and override `.env` values. Secret must be a JSON object:

```json
{
  "GOOGLE_API_KEY": "...",
  "GOOGLE_GEMINI_MODEL": "gemini-2.5-flash",
  "GROQ_API_KEY": "...",
  "GROQ_MODEL": "llama-3.1-8b-instant"
}
```

Both integrations fall back gracefully — S3 errors → local disk, Secrets Manager errors → `.env`.

### IAM Policy Required

```json
{
  "Statement": [
    {"Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::your-bucket"},
    {"Action": ["s3:GetObject", "s3:PutObject"], "Resource": "arn:aws:s3:::your-bucket/*"},
    {"Action": ["secretsmanager:GetSecretValue"], "Resource": "arn:aws:secretsmanager:..."}
  ]
}
```

---

## 11. Knowledge Base

| File | Type | Purpose |
|---|---|---|
| `runbooks/HIGH_CPU_RUNBOOK.md` | Runbook | CPU > 90% — P2 |
| `runbooks/DISK_SPACE_RUNBOOK.md` | Runbook | Disk > 85% — P2/P1 |
| `runbooks/SERVICE_DOWN_RUNBOOK.md` | Runbook | Health check failure — P1 |
| `runbooks/NETWORK_LATENCY_RUNBOOK.md` | Runbook | Latency > 200ms — P2 |
| `runbooks/PERMISSION_OWNERSHIP_DRIFT_RUNBOOK.md` | Runbook | Permission drift — P1/P2 |
| `runbooks/UCD_AGENT_OFFLINE_RUNBOOK.md` | Runbook | IBM UCD agent offline — P2/P3 |
| `incidents/INC-2847-HIGH-CPU-BATCH-JOB.md` | Post-mortem | CPU spike — runaway batch job |
| `incidents/INC-3012-CPU-MISSING-INDEX.md` | Post-mortem | CPU spike — missing DB index |
| `incidents/INC-3301-CONNECTION-POOL-EXHAUSTION.md` | Post-mortem | 503 errors — connection leak |
| `incidents/INC-3455-DISK-FULL-LOGS.md` | Post-mortem | Disk full — log rotation failure |
| `incidents/INC-3601-SERVICE-DOWN-BAD-DEPLOY.md` | Post-mortem | Payment down — bad env var |
| `incidents/INC-4201-UCD-AGENT-OFFLINE-OOM.md` | Post-mortem | UCD agent OOM kill |
| `docs/ESCALATION_POLICY.md` | Policy | P1–P4 escalation paths, SLAs |
| `docs/ALERT_DEFINITIONS.md` | Reference | 30 alert definitions |

---

## 12. API Reference

### `POST /query` / `POST /query/stream`
Triage query. Stream version returns SSE tokens.

**Request:** `{"query": "...", "history": [{"role": "user", "text": "..."}]}`
**Response:** `{"answer": "...", "sources": [...], "chunks_used": 6, "severity": "P2", "elapsed_ms": 2840}`

### `POST /report`
Generate incident post-mortem. **Request:** `{"query": "...", "conversation": "..."}`

### `POST /generate/iac`
Generate Terraform, Ansible, K8s, shell, Prometheus templates.
**Request:** `{"query": "...", "conversation": "..."}`

### `POST /generate/runbook`
Generate a complete runbook `.md` from a resolved conversation.
**Request:** `{"query": "...", "conversation": "..."}`

### `POST /orchestrate`
Generate a branching investigation + remediation workflow.
**Request:** `{"query": "...", "history": [...]}`

### `POST /upload`
Upload a document and live re-index. Multipart form with `file` + `folder` fields.
`folder` must be one of: `runbooks`, `incidents`, `docs`.

### `POST /reindex`
Force full re-index from S3 or local disk without restarting.

### `POST /embed`
Shared embedding endpoint for other apps (e.g. FinPilot).
**Request:** `{"texts": ["text1", "text2"]}` **Response:** `{"embeddings": [[...], [...]]}`

### `GET /health`
Returns index stats, model info, LLM backup status.

### `GET /documents`
Lists all indexed documents with chunk counts.

---

## 13. Features

| Feature | Description |
|---|---|
| **Natural language triage** | Describe any alert in plain English |
| **Runbook retrieval** | Most relevant runbook surfaced in < 2 seconds |
| **Past incident surfacing** | Similar historical incidents with root cause + resolution |
| **Diagnostic commands** | Bash/SQL/kubectl commands ready to copy |
| **Escalation guidance** | Who to page, when, which channel — from policy doc |
| **Source citations** | Every response cites exact documents used |
| **IaC generation** | Terraform, Ansible, K8s manifests, shell scripts, Prometheus rules |
| **Runbook generation** | Auto-generate runbook from resolved triage conversation |
| **Orchestration workflow** | Branching investigation plan with `IF/THEN/ELSE` decision trees |
| **Groq fallback** | Auto-fallback to Groq on any Gemini error (rate limit, deprecated model, etc.) |
| **S3 document storage** | Documents survive container rebuilds — editable without SSH |
| **Secrets Manager** | API keys stored securely — rotatable without server access |
| **Folder-aware upload** | Upload goes to correct S3 prefix based on document type |
| **Force reindex** | `/reindex` endpoint picks up new S3 files without restart |
| **Shared embed endpoint** | `/embed` lets other co-hosted apps reuse the loaded model |

---

## 14. File Structure

```
watsonx/
│
├── app/                          Application code
│   ├── main.py                   FastAPI backend — RAG engine, all endpoints
│   ├── vector_store.py           Persistence layer — NumPy+JSON index
│   ├── aws.py                    AWS integration — S3 + Secrets Manager
│   ├── requirements.txt          Python dependencies
│   ├── .env                      API keys (not committed)
│   ├── .env.example              Key template
│   ├── README.md                 Quick start guide
│   └── static/
│       └── index.html            Single-page frontend
│
├── runbooks/                     Runbook documents (indexed)
├── incidents/                    Incident post-mortems (indexed)
├── docs/                         Policy and reference documents (indexed)
├── demo/                         Demo scripts and talking points
├── guides/                       IBM Bob and setup guides
├── scripts/
│   └── s3_sync.py                One-time script to seed S3 from local files
│
├── Dockerfile                    Multi-stage Docker build (CPU-only torch)
├── docker-compose.yml            Single-service compose with AWS env passthrough
├── .dockerignore                 Excludes .env, __pycache__, vector_store
├── deploy.sh                     One-time EC2 bootstrap script
│
├── .github/
│   └── workflows/
│       └── deploy.yml            CI/CD — auto-deploy to EC2 on push to main
│
└── PRODUCT_DOCUMENTATION.md      This file
```

---

## 15. Setup & Run

### Local Development

```powershell
cd app
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with your API keys
python -m uvicorn main:app --port 8000
# Open http://localhost:8000
```

### Docker (local)

```bash
docker compose up -d --build
# Open http://localhost:8080
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GOOGLE_API_KEY` | — | Gemini API key (or set via Secrets Manager) |
| `GOOGLE_GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `GROQ_API_KEY` | — | Groq fallback key (optional) |
| `GROQ_MODEL` | `llama-3.1-8b-instant` | Groq model name |
| `AWS_REGION` | `us-east-1` | AWS region |
| `S3_BUCKET_NAME` | — | S3 bucket (leave blank for local disk) |
| `SECRETS_MANAGER_ARN` | — | Secrets Manager ARN (leave blank for .env) |

---

## 16. Deployment

### Infrastructure

- **AWS EC2 t3.small** — 2 vCPU, 2GB RAM, 20GB EBS, Ubuntu 22.04
- **2GB swap file** — required for sentence-transformers index build on 2GB RAM
- **Docker + Docker Compose** — containerised, auto-restarts on failure
- **IAM instance profile** — grants S3 + Secrets Manager access without access keys

### GitHub Actions CI/CD

Push to `main` → GitHub Actions SSHs into EC2 → `git pull` → `docker compose up -d --build` → health check.

**Required GitHub secrets:**

| Secret | Value |
|---|---|
| `EC2_HOST` | EC2 public IP |
| `EC2_USER` | `ubuntu` |
| `EC2_SSH_KEY` | Contents of `.pem` private key |

### First Deploy on EC2

```bash
git clone https://github.com/YOUR_ORG/YOUR_REPO.git ~/Incident-Triage-Assistant
cd ~/Incident-Triage-Assistant
chmod +x deploy.sh && sudo ./deploy.sh   # installs Docker, systemd, firewall

# Add swap
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Create .env
nano .env   # add AWS_REGION, S3_BUCKET_NAME, SECRETS_MANAGER_ARN

sudo docker compose up -d --build
```

---

## 17. Known Limitations & Future Work

### Current Limitations

| Limitation | Impact |
|---|---|
| t3.small RAM (2GB) | Requires swap file for index build; OOM risk under heavy load |
| `.md` / `.txt` only | PDF and Word documents not supported |
| No authentication | No access control — suitable for internal/demo use only |
| Re-index on S3 drop | Dropping a file in S3 requires calling `POST /reindex` or restart |
| Single uvicorn worker | Sequential LLM calls under concurrent load |

### Future Enhancements

#### Near-Term
- **S3 event → Lambda → `/reindex`** — zero-touch runbook publishing (infrastructure planned)
- **DynamoDB session persistence** — triage sessions survive browser refresh, shareable by link
- **SNS P1/P2 alerts** — fire email/SMS when a P1 query is submitted
- **Confidence score filter** — warn engineer when top chunk scores below similarity threshold

#### Medium-Term
- **Incremental re-index** — embed only new/changed documents, not full rebuild
- **PDF / Word ingestion** — `pymupdf` + `python-docx` for Confluence export support
- **IBM watsonx.ai Granite** — swap Gemini for `ibm/granite-3-8b-instruct` via `ibm-watsonx-ai` SDK

#### Longer-Term
- **Multi-user auth** — JWT or SSO, per-engineer session isolation
- **Live de-index** — remove documents via UI without restart
- **Horizontal scaling** — multiple workers behind a load balancer with shared S3 index
