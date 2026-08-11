# Infrastructure Incident Triage Assistant

IBM Bob-powered RAG assistant for on-call infrastructure engineers.

## Quick Start

```powershell
cd C:\Users\0025BL744\Desktop\watsonx\app

# First time only — create .env
Set-Content .env "GOOGLE_API_KEY=AIzaSyB1_h4g0UmgekQe_Fgnzx5VAwYR_TGZrsY`nGOOGLE_GEMINI_MODEL=gemini-2.5-flash"

# Start the server
python -m uvicorn main:app --port 8080

# Open in browser
start http://localhost:8080
```

## Features

| Feature | Description |
|---|---|
| **Streaming responses** | Answers stream word-by-word via SSE (toggle in header) |
| **Conversation memory** | Last 3 exchanges sent with each query — follow-up questions work |
| **Persistent vector index** | NumPy+JSON index saved to `app/vector_store/` — starts in <200ms after first build |
| **Response time badge** | Per-message latency shown in green/yellow/orange |
| **Severity detection** | P1/P2/P3/P4 banner auto-detected from query keywords |
| **Incident report** | Full post-mortem report generated on demand |
| **Document upload** | Drop a `.md` file to add to the knowledge base live |

## Tech Stack

- **Backend**: FastAPI + Python
- **LLM**: Google Gemini 2.5 Flash (via `google-generativeai`)
- **Embeddings**: `all-MiniLM-L6-v2` via `sentence-transformers` (local, no API key)
- **Vector index**: NumPy cosine similarity + JSON persistence (no DB required)
- **Frontend**: Single-page HTML/CSS/JS (no framework)

## Architecture

```
User query
    │
    ├─ Severity detection (regex keyword matching)
    │
    ├─ Embed query (all-MiniLM-L6-v2, local)
    │
    ├─ Cosine similarity search over 315 chunks
    │   (loaded from disk in <200ms on subsequent starts)
    │
    ├─ Top-6 chunks injected into Gemini prompt
    │   (with conversation history for multi-turn)
    │
    └─ Response streamed via SSE → rendered in real-time
```

## Knowledge Base

| Folder | Documents |
|---|---|
| `runbooks/` | HIGH_CPU, DISK_SPACE, SERVICE_DOWN, NETWORK_LATENCY |
| `incidents/` | INC-2847, INC-3012, INC-3301, INC-3455, INC-3601 |
| `docs/` | ESCALATION_POLICY, ALERT_DEFINITIONS |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Frontend UI |
| `GET` | `/health` | Index stats + model info |
| `POST` | `/query` | Standard query (returns full answer) |
| `POST` | `/query/stream` | Streaming query (SSE) |
| `POST` | `/report` | Generate incident post-mortem |
| `POST` | `/upload` | Upload + re-index a document |
| `GET` | `/documents` | List all indexed documents |

## Persistent Index

On first start, all 315 chunks are embedded (~30-60s).
The index is saved to `app/vector_store/` (chunks.json + embeddings.npy).
On subsequent starts, the index loads from disk in <200ms.
The index rebuilds automatically when documents change (fingerprint-based detection).

## Adding New Runbooks

1. Drop a `.md` file into `runbooks/`, `incidents/`, or `docs/`
2. Restart the server (auto-detects new files via fingerprint)
   **or** use the Upload button in the UI for live re-indexing

## Requirements

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
python-dotenv==1.0.1
google-generativeai==0.7.2
sentence-transformers==3.0.1
numpy==1.26.4
```
