# Infrastructure Incident Triage Assistant
### Product Documentation v2.1

**Project:** IBM WatsonX Challenge — Use Case 2
**Built with:** FastAPI · Google Gemini 2.0 Flash · Sentence Transformers · NumPy
**Status:** MVP — Demo Ready
**Last Updated:** 2025-06-01

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
10. [Knowledge Base](#10-knowledge-base)
11. [API Reference](#11-api-reference)
12. [Features](#12-features)
13. [Demo Scenarios](#13-demo-scenarios)
14. [File Structure](#14-file-structure)
15. [Setup & Run](#15-setup--run)
16. [Known Limitations & Future Work](#16-known-limitations--future-work)

---

## 1. Product Overview

The **Infrastructure Incident Triage Assistant** is a locally-hosted, RAG-powered AI assistant for on-call infrastructure engineers. It eliminates the 30–60 minute context-gathering phase that precedes every production incident by instantly surfacing the relevant runbook, past incident history, diagnostic commands, and escalation guidance — all grounded in your actual operational documentation.

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

A single-page web application running locally that:

- Ingests all infrastructure documentation (runbooks, post-mortems, policies) at startup
- Builds a persistent local vector index — loads from disk in < 200ms on subsequent starts
- Accepts natural language queries from the engineer
- Retrieves the top 6 most semantically relevant document chunks
- Sends conversation history with each query for multi-turn follow-up support
- Injects retrieved chunks + history into a structured prompt sent to Google Gemini 2.0 Flash
- Streams the response word-by-word via Server-Sent Events
- Detects incident severity (P1–P4) automatically from the alert description
- Generates a complete incident post-mortem report on demand
- Allows new runbooks to be uploaded and indexed live without restarting
- Persists full chat session history in the browser (localStorage) with automatic save, replay, and similar-session surfacing

---

## 4. Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Engineer's Browser                        │
│                   http://localhost:8080                      │
│             (index.html — Single Page App)                   │
└───────────────────┬─────────────────────────────────────────┘
                    │ HTTP POST /query/stream  (SSE)
                    │ HTTP POST /query         (standard)
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Backend (main.py)                   │
│                                                             │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │ /query       │  │ /report     │  │ /upload          │   │
│  │ /query/stream│  │ (post-mortem│  │ (live re-index)  │   │
│  └──────┬───────┘  └──────┬──────┘  └────────┬─────────┘   │
│         │                 │                  │              │
│         ▼                 ▼                  ▼              │
│  ┌────────────────────────────────────────────────────┐     │
│  │                  RAG Pipeline                       │     │
│  │  1. Severity detection (keyword, instant)           │     │
│  │  2. Embed query (all-MiniLM-L6-v2, local)          │     │
│  │  3. Cosine similarity search (NumPy, < 5ms)         │     │
│  │  4. Retrieve top-6 chunks                           │     │
│  │  5. Build prompt: system + history + context        │     │
│  │  6. Stream Gemini response via SSE                  │     │
│  └────────────────────────────────────────────────────┘     │
│                                                             │
│  ┌────────────────────────────────────────────────────┐     │
│  │           Persistent Vector Index                   │     │
│  │  vector_store/chunks.json  — chunk metadata         │     │
│  │  vector_store/embeddings.npy — float32 [N × 384]   │     │
│  │  vector_store/fingerprint.txt — staleness check     │     │
│  │  Loads from disk in < 200ms on restart              │     │
│  └────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
                    │ HTTPS API call
                    ▼
┌─────────────────────────────────────────────────────────────┐
│           Google Gemini 2.0 Flash (Cloud API)               │
│  Receives: system prompt + conversation history + context   │
│  Returns: grounded markdown response (streamed)             │
└─────────────────────────────────────────────────────────────┘
```

### Startup Sequence

```
Server starts
     │
     ├─ Load .env (GOOGLE_API_KEY, GOOGLE_GEMINI_MODEL)
     ├─ Initialise Gemini client
     ├─ Load all-MiniLM-L6-v2 embedding model (cached after first run)
     ├─ Scan runbooks/*.md + incidents/*.md + docs/*.md
     ├─ Check vector_store/fingerprint.txt
     │   ├─ MATCH  → load chunks.json + embeddings.npy from disk (< 200ms)
     │   └─ STALE  → re-embed all chunks → save to disk (~30-60s, once only)
     └─ FastAPI server ready → http://localhost:8080
```

### Query Flow (Streaming)

```
Engineer types: "CPU usage on prod-db-01 is at 98%"
     │
     ├─ [Frontend]  POST /query/stream {query, history:[...]}
     ├─ [Backend]   detect_severity() → "P2"
     ├─ [Backend]   embedder.encode(query) → 384-dim vector
     ├─ [Backend]   cosine_search() → top 6 chunk indices
     ├─ [Backend]   Build prompt: SYSTEM + context + last 3 exchanges
     ├─ [Backend]   gemini.generate_content(prompt, stream=True)
     ├─ [SSE]       → data: {"type":"meta", "severity":"P2", "sources":[...]}
     ├─ [SSE]       → data: {"type":"token", "text":"## Immediate..."} × N
     ├─ [SSE]       → data: {"type":"done", "elapsed_ms": 2340}
     └─ [Frontend]  Render severity banner + streaming markdown + sources bar
```

---

## 5. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **LLM** | Google Gemini 2.0 Flash | Latest | Response generation (streaming) |
| **Embeddings** | sentence-transformers / all-MiniLM-L6-v2 | 3.0.1 | Local vector embedding (free, no API) |
| **Vector Search** | NumPy cosine similarity + JSON persistence | 1.26.4 | Nearest-neighbour search + disk persistence |
| **Backend** | FastAPI | 0.111.0 | REST API + SSE streaming server |
| **ASGI Server** | Uvicorn | 0.30.1 | HTTP server |
| **Frontend** | Vanilla HTML/CSS/JS | — | Single page app (zero dependencies, no build step) |
| **Config** | python-dotenv | 1.0.1 | Environment variable loading |
| **Language** | Python | 3.12 | Backend runtime |

---

## 6. Backend

**Files:** `app/main.py`, `app/vector_store.py`

### main.py — Responsibilities

```
main.py
├── Configuration loading (.env)
├── Gemini client initialisation (gemini-2.0-flash)
├── Embedding model loading (SentenceTransformer)
├── Document loading        load_documents()
├── Document chunking       chunk_document()
├── Index building          build_index()  — persistent via vector_store.py
├── Vector search           retrieve()
├── Severity detection      detect_severity()
├── Prompt construction     build_prompt()  — includes conversation history
├── Rate limit handling     _parse_retry_delay() + ResourceExhausted catch
└── FastAPI app + routes
    ├── GET  /                → serve index.html
    ├── GET  /health          → index stats + model + backend type
    ├── POST /query           → standard triage response
    ├── POST /query/stream    → SSE streaming triage response
    ├── POST /report          → incident post-mortem generation
    ├── POST /upload          → upload + live re-index document
    └── GET  /documents       → list all indexed documents
```

### vector_store.py — Persistence Layer

```
vector_store.py
├── save_index(chunks, embeddings, sources)  → writes chunks.json + embeddings.npy
├── load_index()                             → reads from disk, returns in < 200ms
├── is_index_current(sources)               → MD5 fingerprint staleness check
└── cosine_search(query_vec, embeddings, k) → returns top-k indices + scores
```

Storage files (auto-created inside `app/vector_store/`):

| File | Contents |
|---|---|
| `chunks.json` | List of chunk dicts: `{text, source, folder, start}` |
| `embeddings.npy` | float32 NumPy array, shape `(315, 384)` |
| `fingerprint.txt` | MD5 hash of sorted document source paths |

### Chunking Strategy

```
CHUNK_SIZE    = 500   characters per chunk
CHUNK_OVERLAP = 100   overlap between consecutive chunks
Min length    = 60    shorter chunks discarded (headers, blank lines)
```

Chunks break at the nearest newline within the last 50% of the window, preserving markdown structure. Each chunk carries `source`, `folder`, `start` metadata.

### Conversation Memory

The last 6 messages (3 exchanges) are sent with every query:

```python
class QueryRequest(BaseModel):
    query: str
    history: Optional[List[HistoryItem]] = []   # [{role, text}, ...]
```

History is injected into the prompt as a `## Conversation History` section, enabling follow-up questions like *"what about the disk version of that?"* to resolve correctly.

### Severity Detection

Keyword-based pre-classification runs before the LLM call:

| Severity | Keywords |
|---|---|
| P1 | `critical`, `down`, `outage`, `payment`, `unavailable`, `not responding` |
| P2 | `high`, `98%`, `95%`, `degraded`, `slow`, `spike`, `exhausted`, `failing`, `error` |
| P3 | `warning`, `85%`, `growing`, `disk`, `latency` |
| P4 | `low`, `informational`, `minor` |

### Error Handling

`ResourceExhausted` (Gemini rate limit) is caught on all three LLM calls and returns a friendly message with the retry countdown rather than a 500 error.

---

## 7. Frontend

**File:** `app/static/index.html`

A single self-contained HTML file — no React, no npm, no build step.

### Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Header: title · IBM Bob badge · status · Streaming toggle · Clear│
├───────────────────────┬──────────────────────────────────────────┤
│                       │                                           │
│  Sidebar              │         Chat Messages                     │
│  ┌──────┬──────────┐  │                                           │
│  │Knowl-│ History  │  │  [Welcome screen with 4 scenario cards]   │
│  │edge  │          │  │  or                                       │
│  └──────┴──────────┘  │  [Message bubbles — user right, BOB left] │
│                       │                                           │
│  [Knowledge tab]      ├───────────────────────────────────────────│
│   Runbooks (5)        │  Quick prompt chips                       │
│   Incidents (5)       ├───────────────────────────────────────────│
│   Policies (2)        │  [Textarea]                    [Send]     │
│   Upload Zone         │                                           │
│   Index badge         │                                           │
│                       │                                           │
│  [History tab]        │                                           │
│   + New Chat btn      │                                           │
│   Similar sessions    │                                           │
│   Session list        │                                           │
│   (scrollable)        │                                           │
└───────────────────────┴───────────────────────────────────────────┘
                         Report Modal (overlay, on demand)
```

### Key UI Components

| Component | Description |
|---|---|
| **Streaming toggle** | Checkbox in header — switches between SSE streaming and standard request |
| **Severity banner** | Coloured banner (red P1 / orange P2 / blue P3 / grey P4) at top of each response |
| **Streaming cursor** | Blinking blue cursor while Gemini is generating |
| **Response time badge** | Per-message latency: green < 3s, yellow 3–8s, orange > 8s |
| **Code blocks** | Syntax-highlighted with hover-reveal Copy button |
| **Source chips** | Document filename chips at the bottom of each response |
| **Generate Report** | Button in sources bar — triggers post-mortem modal |
| **Upload zone** | Drag-and-drop or click-to-browse; shows live re-index status |
| **Index badge** | Sidebar shows `numpy+json (persistent)` backend confirmation |
| **Quick prompts** | Pre-built chips for common queries |
| **Welcome screen** | Four scenario cards that auto-fill and submit on click |
| **Clear chat** | Saves current session then resets to welcome screen |
| **Sidebar tabs** | Knowledge tab (docs + upload) and History tab (past sessions) |
| **Chat history panel** | Scrollable list of past sessions — grouped Today / Earlier, click to replay |
| **Session cards** | Title, severity pill, exchange count, relative timestamp, delete button |
| **Session replay** | Loads any past session back into the chat pane with full message rendering |
| **Similar sessions banner** | After each reply, surfaces up to 3 related past sessions by severity + keyword match |
| **+ New Chat button** | Saves current session and resets to a fresh conversation |

---

## 8. RAG Pipeline

### Step-by-Step Pipeline

```
INGEST (at startup)
  Read .md files → Split into 500-char overlapping chunks
  → Embed each chunk with all-MiniLM-L6-v2 (local)
  → Save to disk as chunks.json + embeddings.npy
  → On restart: load from disk in < 200ms (no re-embedding)

RETRIEVE (per query)
  Embed query → 384-dim vector
  → Cosine similarity vs all N chunk vectors (single matrix multiply, < 5ms)
  → Return top-6 chunks by similarity score

AUGMENT (per query)
  Build prompt:
    SYSTEM_PROMPT (role + output format rules)
    + Retrieved context (top-6 chunks, each labelled with source + score)
    + Conversation history (last 3 exchanges)
    + Current query

GENERATE (per query)
  Stream prompt to Gemini 2.0 Flash
  → Tokens streamed back via SSE as they arrive
  → Frontend renders markdown incrementally
```

### Retrieval Parameters

| Parameter | Value | Rationale |
|---|---|---|
| `TOP_K` | 6 | Covers runbook + 2 incidents + policy without bloating context |
| `CHUNK_SIZE` | 500 chars | ~3–5 runbook steps per chunk |
| `CHUNK_OVERLAP` | 100 chars | Prevents boundary splits losing context |
| Min chunk | 60 chars | Filters out headers and blank lines |
| History window | 6 messages | Last 3 exchanges (user + assistant) |

---

## 9. Vector Index

### Implementation — NumPy + JSON Persistence

```python
# vector_store/
#   chunks.json       — 315 chunk dicts
#   embeddings.npy    — float32 array (315, 384) = ~0.5 MB
#   fingerprint.txt   — MD5 of sorted source paths

def cosine_search(query_vec, embeddings, top_k):
    q = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    normed = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-10)
    scores = normed @ q          # single matrix multiply → scores for all 315 chunks
    return argsort(scores)[-top_k:], scores
```

### Index Statistics

| Metric | Value |
|---|---|
| Total documents | 11 |
| Total chunks | 315 |
| Embedding dimensions | 384 |
| Vector array size on disk | ~0.5 MB |
| Embedding model size | ~90 MB (cached after first download) |
| Index build time (first run) | ~30–60 seconds |
| Index load time (subsequent) | **< 200ms** |
| Query retrieval time | < 5ms |

### Persistence Logic

```
Startup
  ├─ Scan docs → compute MD5 fingerprint of source list
  ├─ Read vector_store/fingerprint.txt
  │   ├─ Matches → load_index() from disk (< 200ms)
  │   └─ Mismatch → re-embed all → save_index() → update fingerprint
  └─ Server ready
```

---

## 10. Knowledge Base

### Document Inventory

| File | Type | Purpose |
|---|---|---|
| `runbooks/HIGH_CPU_RUNBOOK.md` | Runbook | CPU > 90% triage — P2 |
| `runbooks/DISK_SPACE_RUNBOOK.md` | Runbook | Disk > 85% triage — P2/P1 |
| `runbooks/SERVICE_DOWN_RUNBOOK.md` | Runbook | Health check failure — P1 |
| `runbooks/NETWORK_LATENCY_RUNBOOK.md` | Runbook | Latency > 200ms — P2 |
| `runbooks/PERMISSION_OWNERSHIP_DRIFT_RUNBOOK.md` | Runbook | Recursive chmod/chown — permission drift — P1/P2 |
| `incidents/INC-2847-HIGH-CPU-BATCH-JOB.md` | Post-mortem | CPU spike — runaway batch job — P2 |
| `incidents/INC-3012-CPU-MISSING-INDEX.md` | Post-mortem | CPU spike — missing DB index — P1 |
| `incidents/INC-3301-CONNECTION-POOL-EXHAUSTION.md` | Post-mortem | 503 errors — connection leak — P2 |
| `incidents/INC-3455-DISK-FULL-LOGS.md` | Post-mortem | Disk full — log rotation failure — P3 |
| `incidents/INC-3601-SERVICE-DOWN-BAD-DEPLOY.md` | Post-mortem | Payment down — bad env var — P1 |
| `docs/ESCALATION_POLICY.md` | Policy | P1–P4 escalation paths, SLAs, contacts |
| `docs/ALERT_DEFINITIONS.md` | Reference | 30 alert definitions, thresholds, owners |

### Adding New Documents

1. Drop a `.md` or `.txt` file into `runbooks/`, `incidents/`, or `docs/`
2. **Restart the server** — fingerprint mismatch triggers automatic re-index
   **or** use the **Upload Zone** in the sidebar for live re-index without restart

---

## 11. API Reference

### `POST /query`

Standard triage query. Returns full answer after generation completes.

**Request:**
```json
{
  "query": "CPU usage on prod-db-01 is at 98% for 12 minutes",
  "history": [
    {"role": "user", "text": "previous question"},
    {"role": "assistant", "text": "previous answer"}
  ]
}
```

**Response:**
```json
{
  "answer": "## Immediate Actions\n1. Acknowledge...",
  "sources": ["runbooks/HIGH_CPU_RUNBOOK.md", "incidents/INC-2847-HIGH-CPU-BATCH-JOB.md"],
  "chunks_used": 6,
  "severity": "P2",
  "elapsed_ms": 2840
}
```

---

### `POST /query/stream`

Streaming triage via Server-Sent Events. Response arrives token-by-token.

**Request:** Same as `/query`

**SSE Event stream:**
```
data: {"type":"meta", "severity":"P2", "sources":[...], "chunks_used":6}

data: {"type":"token", "text":"## Immediate Actions\n"}

data: {"type":"token", "text":"1. Acknowledge the alert..."}

... (N token events) ...

data: {"type":"done", "elapsed_ms":2340}
```

On rate limit: emits a `token` event with a friendly error message, then `done`.

---

### `POST /report`

Generate a full incident post-mortem report from a triage conversation.

**Request:**
```json
{
  "query": "CPU usage on prod-db-01 is at 98%",
  "conversation": "USER: CPU usage...\nASSISTANT: ## Immediate Actions..."
}
```

**Response:**
```json
{ "report": "# Incident Report — Production DB CPU Spike\n## Summary\n..." }
```

---

### `GET /health`

Returns index and model statistics.

**Response:**
```json
{
  "status": "ok",
  "documents_indexed": 11,
  "total_chunks": 315,
  "embedding_model": "all-MiniLM-L6-v2",
  "llm": "gemini-2.0-flash",
  "index_backend": "numpy+json (persistent)"
}
```

---

### `POST /upload`

Upload a `.md` or `.txt` file and live re-index the knowledge base.

**Request:** `multipart/form-data` with field `file`

**Response:**
```json
{
  "message": "NEW_RUNBOOK.md uploaded and indexed successfully",
  "total_chunks": 347,
  "total_documents": 12
}
```

---

### `GET /documents`

Lists all indexed documents with chunk counts.

**Response:**
```json
{
  "documents": [
    { "source": "runbooks/HIGH_CPU_RUNBOOK.md", "folder": "runbooks", "chunks": 35 }
  ],
  "total": 11
}
```

---

## 12. Features

### Core Features

| Feature | Description |
|---|---|
| **Natural language triage** | Describe any alert in plain English |
| **Runbook retrieval** | Surfaces the most relevant runbook in < 2 seconds |
| **Past incident surfacing** | Retrieves similar historical incidents with root cause and resolution |
| **Diagnostic commands** | Returns actual bash/SQL/kubectl commands ready to copy and run |
| **Escalation guidance** | States who to page, when, and via which channel — from policy doc |
| **Source citations** | Every response cites the exact document(s) it used |
| **Conversation memory** | Last 3 exchanges sent with each query — follow-up questions work |
| **Chat session history** | All conversations auto-saved to browser localStorage; survives page refresh |

### UI Features

| Feature | Description |
|---|---|
| **Streaming responses** | Answer appears word-by-word via SSE — toggle in header |
| **Response time badge** | Per-message latency badge: green/yellow/orange |
| **Severity badge** | Auto-detected P1/P2/P3/P4 coloured banner |
| **Copy button on code blocks** | Hover to reveal — copies raw command to clipboard |
| **Incident report generator** | "Generate Report" on every response — opens post-mortem modal |
| **File upload** | Drag-and-drop zone — live re-index without restart |
| **Persistent index badge** | Sidebar confirms index backend type |
| **Quick prompts** | Pre-built chips for 5 common queries |
| **Welcome scenarios** | Four clickable alert scenarios to start a demo |
| **Clear chat** | Saves current session then resets to welcome screen |
| **Live status bar** | Header shows doc count, chunk count, active model |
| **Chat history panel** | History tab in sidebar — scrollable past sessions grouped Today / Earlier |
| **Session replay** | Click any past session to reload full conversation with severity banners intact |
| **Similar sessions** | After each response, surfaces related past sessions by severity + keyword |
| **+ New Chat** | Saves current session and opens a fresh conversation |

---

## 13. Demo Scenarios

These six queries demonstrate the full capability:

```
1. "CPU usage on prod-db-01 is at 98% for the last 12 minutes"
   → P2 banner · HIGH_CPU_RUNBOOK steps · INC-2847 + INC-3012 history · escalation path

2. "Payment service health check has been failing for 5 minutes, 503 errors"
   → P1 banner · SERVICE_DOWN_RUNBOOK · INC-3601 rollback steps · P1 escalation

3. "Disk usage on prod-app-03 is at 92% and still growing"
   → P2 banner · DISK_SPACE_RUNBOOK · INC-3455 · cleanup commands

4. "Has a CPU spike like this happened before on prod-db?"
   → INC-2847 + INC-3012 · root causes · resolutions (multi-turn follow-up)

5. "Who do I escalate a P1 incident to and what are the steps?"
   → Full P1 escalation path from ESCALATION_POLICY.md

6. "What is the rollback procedure for a bad Kubernetes deployment?"
   → kubectl rollout undo steps from SERVICE_DOWN_RUNBOOK + INC-3601
```

**Multi-turn demo sequence:**
```
Query 1: "CPU usage on prod-db-01 is at 98%"
Query 2: "What were the past incidents like this?"
Query 3: "How long did INC-3012 take to resolve?"
→ Each follow-up resolves correctly using conversation history
```

---

## 14. File Structure

```
watsonx/
│
├── app/                              Application code
│   ├── main.py                       FastAPI backend — RAG engine, SSE streaming
│   ├── vector_store.py               Persistence layer — NumPy+JSON index
│   ├── requirements.txt              Python dependencies (6 packages)
│   ├── .env                          API keys (not committed to git)
│   ├── .env.example                  Key template
│   ├── README.md                     Quick start guide
│   ├── static/
│   │   └── index.html                Single-page frontend (no dependencies)
│   └── vector_store/                 Auto-created on first run
│       ├── chunks.json               315 chunk metadata dicts
│       ├── embeddings.npy            float32 array (315, 384)
│       └── fingerprint.txt           MD5 staleness fingerprint
│
├── runbooks/                         Runbook documents (indexed)
│   ├── HIGH_CPU_RUNBOOK.md
│   ├── DISK_SPACE_RUNBOOK.md
│   ├── SERVICE_DOWN_RUNBOOK.md
│   ├── NETWORK_LATENCY_RUNBOOK.md
│   └── PERMISSION_OWNERSHIP_DRIFT_RUNBOOK.md
│
├── incidents/                        Incident post-mortems (indexed)
│   ├── INC-2847-HIGH-CPU-BATCH-JOB.md
│   ├── INC-3012-CPU-MISSING-INDEX.md
│   ├── INC-3301-CONNECTION-POOL-EXHAUSTION.md
│   ├── INC-3455-DISK-FULL-LOGS.md
│   └── INC-3601-SERVICE-DOWN-BAD-DEPLOY.md
│
├── docs/                             Policy and reference documents (indexed)
│   ├── ESCALATION_POLICY.md
│   └── ALERT_DEFINITIONS.md
│
├── schema/                           ICA Context Studio schema (reference)
│   ├── IncidentTriageSchema.jsonld
│   ├── IncidentTriageSchema_Graph.jsonld
│   └── sample_data.json
│
├── guides/                           Setup guides
│   ├── ICA_CONTEXT_STUDIO_SETUP.md
│   ├── IBM_BOB_CONFIGURATION.md
│   └── SCHEMA_BUILDER_GUIDE.md
│
├── demo/                             Presentation materials
│   ├── DEMO_SCRIPT.md
│   └── PITCH_TALKING_POINTS.md
│
└── PRODUCT_DOCUMENTATION.md         This file
```

---

## 15. Setup & Run

### Prerequisites

- Python 3.10+
- Google Gemini API key — free at https://aistudio.google.com/app/apikey
- Internet connection on first run only (downloads ~90MB embedding model, cached after)

### Installation

```powershell
# 1. Navigate to app directory
cd C:\Users\...\watsonx\app

# 2. Install dependencies (global Python or venv)
pip install -r requirements.txt

# 3. Create .env file with your API key
Set-Content .env "GOOGLE_API_KEY=YOUR_KEY_HERE`nGOOGLE_GEMINI_MODEL=gemini-2.0-flash"
```

### Run

```powershell
python -m uvicorn main:app --port 8080
```

Open browser: **http://localhost:8080**

### First Run vs Subsequent Runs

| | First run | Subsequent runs |
|---|---|---|
| Embedding model | Downloads ~90MB (once, cached) | Loads from cache instantly |
| Vector index | Embeds 315 chunks (~30–60s) | Loads from disk (< 200ms) |
| Server ready | ~60–90 seconds | **~3–5 seconds** |

---

## 16. Known Limitations & Future Work

### Current Limitations

| Limitation | Impact |
|---|---|
| Gemini free tier quota | 50–1500 req/day depending on model; rate limit shows friendly message in UI |
| `.md` / `.txt` only | PDF and Word documents not supported for upload |
| No authentication | Single-user, localhost only — no access control |
| Keyword severity detection | Can misclassify edge cases; LLM re-confirms in response |
| Chat history is browser-local | History stored in `localStorage` — not shared across devices or engineers |
| No live de-index | Removing a document requires deleting the file and restarting the server |

### Future Enhancements Planned

#### 🔵 Near-Term (Low Effort / High Value)

| Enhancement | Description | Effort |
|---|---|---|
| **Save from Chat** | Type `save this as an incident` or `store this as a runbook` in the chat — the assistant generates a properly formatted `.md` document from the conversation, saves it to `incidents/` or `runbooks/`, and live re-indexes it immediately | Low |
| **Confidence Score Filter** | Surface a "Low confidence" warning in the UI when the top retrieved chunk scores below a cosine similarity threshold (e.g. `< 0.4`) — tells the engineer the assistant is extrapolating, not citing a known runbook | Very Low |
| **Runbook Gap Detector** | A sidebar button or `GET /gaps` endpoint that compares every alert in `ALERT_DEFINITIONS.md` against indexed runbooks and reports which alerts have no matching runbook | Low |
| **IBM watsonx.ai Granite swap-in** | Replace Gemini with `ibm/granite-3-8b-instruct` via the `ibm-watsonx-ai` SDK — fully on-premise, no external API calls, single change in `main.py` | Low |

#### 🟡 Medium-Term (Medium Effort / High Value)

| Enhancement | Description | Effort |
|---|---|---|
| **Incident Timeline Builder** | After triage, a "Build Timeline" button generates a minute-by-minute chronology from the conversation — ready to paste into a Jira post-mortem or Confluence page | Medium |
| **Incremental re-index** | Embed only new or changed documents rather than rebuilding the full index on every upload — makes live uploads near-instant as the knowledge base grows past ~50 documents | Medium |
| **Server-side chat history** | Move session history from browser `localStorage` to a backend SQLite table — history persists across devices, is shared across the team, and is searchable by keyword or severity | Medium |
| **Alert → Runbook auto-mapping** | Parse the alert definitions table at startup into a lookup map so that an incoming alert name (e.g. `K8sPodCrashLooping`) routes directly to its runbook without needing a natural language query | Medium |

#### 🟢 Longer-Term (Higher Effort / Strategic Value)

| Enhancement | Description | Effort |
|---|---|---|
| **PDF / Word ingestion** | Use `pymupdf` + `python-docx` to ingest Confluence exports, PDF runbooks, and Word post-mortems directly — no manual Markdown conversion needed | Medium–High |
| **Multi-language runbook support** | Tag chunks by language and filter at query time — enables multilingual teams to write runbooks in their own language while preserving retrieval accuracy | High |
| **Live de-index via UI** | Remove a document from the index through the UI without restarting the server — complements the existing live upload capability | Medium |
