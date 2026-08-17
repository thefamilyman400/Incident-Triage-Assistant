# Infrastructure Incident Triage Assistant

RAG-powered AI assistant for on-call infrastructure engineers. Deployed on AWS EC2 via Docker + GitHub Actions.

## Quick Start (Local)

```powershell
cd C:\Users\0025BL744\Desktop\watsonx\app

# First time only — create .env
Copy-Item .env.example .env
# Edit .env and fill in your API keys

# Start the server
python -m uvicorn main:app --port 8000

# Open in browser
start http://localhost:8000
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | Yes* | Google Gemini API key |
| `GOOGLE_GEMINI_MODEL` | No | Model name (default: `gemini-2.5-flash`) |
| `GROQ_API_KEY` | No | Groq fallback LLM key |
| `GROQ_MODEL` | No | Groq model (default: `llama-3.1-8b-instant`) |
| `AWS_REGION` | No | AWS region (default: `us-east-1`) |
| `S3_BUCKET_NAME` | No | S3 bucket for documents — leave blank to use local folders |
| `SECRETS_MANAGER_ARN` | No | Secrets Manager ARN — leave blank to use `.env` keys |

*Not required if `SECRETS_MANAGER_ARN` is set.

## Features

| Feature | Description |
|---|---|
| **Streaming responses** | Answers stream word-by-word via SSE (toggle in header) |
| **Conversation memory** | Last 3 exchanges sent with each query — follow-up questions work |
| **Persistent vector index** | NumPy+JSON index saved to `app/vector_store/` — loads in <200ms after first build |
| **Severity detection** | P1/P2/P3/P4 banner auto-detected from query keywords |
| **Incident report** | Full post-mortem report generated on demand |
| **IaC generation** | Terraform, Ansible, K8s, shell scripts generated from incident context |
| **Runbook generation** | Auto-generate a new runbook `.md` from a resolved triage conversation |
| **Orchestration workflow** | Branching investigation + remediation workflow with decision trees |
| **Document upload** | Drop a `.md` file into any folder (`runbooks/`, `incidents/`, `docs/`) via UI |
| **S3 document storage** | Optionally load documents from S3 — survives container rebuilds |
| **Secrets Manager** | Optionally pull API keys from AWS Secrets Manager |
| **Groq fallback** | Auto-fallback to Groq when Gemini is unavailable or rate-limited |

## Tech Stack

- **Backend**: FastAPI + Python 3.12
- **LLM**: Google Gemini 2.5 Flash (primary) + Groq llama-3.1-8b (fallback)
- **Embeddings**: `all-MiniLM-L6-v2` via `sentence-transformers` (local, no API key)
- **Vector index**: NumPy cosine similarity + JSON persistence
- **Document storage**: Local disk (default) or AWS S3
- **Secrets**: `.env` file (default) or AWS Secrets Manager
- **Frontend**: Single-page HTML/CSS/JS (no framework)
- **Deployment**: Docker + GitHub Actions → AWS EC2

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Frontend UI |
| `GET` | `/health` | Index stats + model info |
| `POST` | `/query` | Standard triage query |
| `POST` | `/query/stream` | Streaming triage via SSE |
| `POST` | `/report` | Generate incident post-mortem |
| `POST` | `/generate/iac` | Generate IaC remediation templates |
| `POST` | `/generate/runbook` | Generate a runbook from resolved conversation |
| `POST` | `/orchestrate` | Generate branching investigation workflow |
| `POST` | `/upload` | Upload + re-index a document (with folder selector) |
| `POST` | `/reindex` | Force full re-index from S3 or disk |
| `POST` | `/embed` | Shared embedding endpoint for other apps |
| `GET` | `/documents` | List all indexed documents |

## Adding New Runbooks

**Via S3 (if configured):**
```bash
aws s3 cp MY_RUNBOOK.md s3://your-bucket/runbooks/MY_RUNBOOK.md
# Then trigger re-index:
curl -X POST http://localhost:8000/reindex
```

**Via UI Upload:** Use the folder selector + upload zone in the sidebar.

**Via local disk:** Drop a `.md` file into `runbooks/`, `incidents/`, or `docs/` and restart.

## Docker

```bash
# Build and run
docker compose up -d --build

# View logs
docker compose logs -f

# Health check
curl http://localhost:8080/health
```

## Deployment

Push to `main` triggers automatic deployment to EC2 via GitHub Actions.
Requires these GitHub secrets: `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`.

## Requirements

See [`requirements.txt`](requirements.txt). Key packages:
```
fastapi, uvicorn, google-generativeai, sentence-transformers, numpy, groq, boto3
```
