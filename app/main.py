import os
import glob
import json
import time
import asyncio
from pathlib import Path
from typing import List, Optional

from google.api_core.exceptions import ResourceExhausted, GoogleAPIError

import numpy as np
import google.generativeai as genai
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

from vector_store import is_index_current, load_index, save_index, cosine_search
from aws import get_api_keys, s3_load_documents, s3_upload_document

# Load .env first so AWS env vars are available, then overlay with Secrets Manager
load_dotenv()

# ── Config — prefer Secrets Manager, fall back to .env / env vars ──
_keys = get_api_keys()
GOOGLE_API_KEY      = _keys["GOOGLE_API_KEY"]
GOOGLE_GEMINI_MODEL = _keys["GOOGLE_GEMINI_MODEL"] or "gemini-2.5-flash"
GROQ_API_KEY        = _keys["GROQ_API_KEY"]
GROQ_MODEL          = _keys["GROQ_MODEL"]
DOCS_DIRS           = ["runbooks", "incidents", "docs"]
CHUNK_SIZE          = 500
CHUNK_OVERLAP       = 100
TOP_K               = 6
EMBED_BATCH_SIZE    = 16   # reduced from 32 to lower peak memory on 1GB instances

# ── Initialise Gemini (primary) ─────────────────────────────────
genai.configure(api_key=GOOGLE_API_KEY)
gemini = genai.GenerativeModel(GOOGLE_GEMINI_MODEL)

# ── Initialise Groq (backup — only if key is set) ───────────────
groq_client = None
if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
        print(f"Groq backup LLM ready ({GROQ_MODEL}).")
    except ImportError:
        print("WARNING: groq package not installed. Run: pip install groq==0.9.0")

# ── Initialise embedding model ──────────────────────────────────
print("Loading embedding model...")
embedder = SentenceTransformer("all-MiniLM-L6-v2")
print("Embedding model ready.")


# ── Document loading & chunking ─────────────────────────────────
def load_documents(base_dir: str = "..") -> List[dict]:
    # Try S3 first; fall back to local disk if S3_BUCKET_NAME is not configured
    s3_docs = s3_load_documents()
    if s3_docs is not None:
        return s3_docs

    # Local disk fallback (original behaviour)
    docs = []
    for folder in DOCS_DIRS:
        path = os.path.join(base_dir, folder, "*.md")
        for filepath in glob.glob(path):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            docs.append({
                "source": os.path.relpath(filepath, base_dir).replace("\\", "/"),
                "content": content,
                "folder": folder,
            })
    print(f"Loaded {len(docs)} documents.")
    return docs


def chunk_document(doc: dict) -> List[dict]:
    text = doc["content"]
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk_text = text[start:end]
        if end < len(text):
            last_nl = chunk_text.rfind("\n")
            if last_nl > CHUNK_SIZE // 2:
                end = start + last_nl + 1
                chunk_text = text[start:end]
        chunks.append({
            "source": doc["source"],
            "folder": doc["folder"],
            "text": chunk_text.strip(),
            "start": start,
        })
        start = end - CHUNK_OVERLAP
    return [c for c in chunks if len(c["text"]) > 60]


def build_index(base_dir: str = ".."):
    """Build or load the persistent vector index."""
    docs = load_documents(base_dir)
    all_chunks = []
    for doc in docs:
        all_chunks.extend(chunk_document(doc))

    doc_sources = [d["source"] for d in docs]

    if is_index_current(doc_sources):
        loaded_chunks, embeddings = load_index()
        print(f"Persistent index loaded instantly — {len(loaded_chunks)} chunks from disk.")
        return loaded_chunks, embeddings

    print(f"Building index for {len(all_chunks)} chunks...")
    texts = [c["text"] for c in all_chunks]
    embeddings = embedder.encode(texts, show_progress_bar=True, batch_size=EMBED_BATCH_SIZE)
    save_index(all_chunks, embeddings, doc_sources)
    print(f"Index built and saved to disk ({len(all_chunks)} chunks).")
    return all_chunks, embeddings


def retrieve(query: str, chunks: List[dict], embeddings: np.ndarray, top_k: int = TOP_K) -> List[dict]:
    q_emb = embedder.encode([query])[0]
    indices, scores = cosine_search(q_emb, embeddings, top_k)
    return [{**chunks[i], "score": float(scores[i])} for i in indices]


# ── Build index at startup ──────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHUNKS, EMBEDDINGS = build_index(BASE_DIR)


# ── Severity detection ──────────────────────────────────────────
def detect_severity(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ["p1","critical","down","outage","payment","completely","100%","unavailable","not responding"]):
        return "P1"
    if any(w in q for w in ["p2","high","98%","95%","92%","degraded","slow","spike","exhausted","failing","error"]):
        return "P2"
    if any(w in q for w in ["p3","medium","warning","85%","growing","disk","latency"]):
        return "P3"
    if any(w in q for w in ["p4","low","informational","minor"]):
        return "P4"
    return "UNKNOWN"


# ── System prompt ───────────────────────────────────────────────
SYSTEM_PROMPT = """You are an Infrastructure Incident Triage Assistant powered by IBM Bob.
Your role is to help on-call engineers quickly diagnose and resolve infrastructure incidents.

When given an alert or incident description you MUST:
1. Identify the most relevant runbook from the context and list its IMMEDIATE ACTIONS step by step
2. Show the most relevant DIAGNOSTIC COMMANDS from the runbook (as code blocks)
3. List PROBABLE ROOT CAUSES based on the runbook
4. Reference any PAST SIMILAR INCIDENTS from the context (include incident ID, severity, root cause, resolution)
5. State ESCALATION criteria and path (who to contact, when, which Slack channel)
6. Suggest 2-3 PROACTIVE IMPROVEMENTS — monitoring gaps, hardening steps, or IaC automation opportunities grounded strictly in the retrieved context

Rules:
- Be concise and actionable — engineers are under pressure
- Always cite your sources at the end using [Source: filename] format
- Use markdown formatting: ## headers, numbered lists, code blocks with ```bash
- If asked a general question (not an alert), answer directly from the context provided
- Never make up incident IDs or runbook steps — only use what is in the context
- If the context does not cover the question, say so clearly
"""

# ── IaC generation prompt ────────────────────────────────────────
IAC_PROMPT = """You are an Infrastructure-as-Code Engineer working with IBM Bob.
Given an incident description and the relevant runbook/incident context, generate
production-ready IaC remediation templates to fix and prevent this incident.

Produce ALL applicable sections below. Mark any section N/A with a one-line reason
if it genuinely does not apply to this incident type.

## IaC Remediation Templates

### Shell Automation Script
A bash script (shebang included) that automates the immediate triage steps from the
runbook — ready to run as a cron job, alert webhook, or first-response script.
Label: `# File: triage_<incident_type>.sh`

### Ansible Playbook
An Ansible play that automates the OS-level or service-level fix across multiple
servers (disk cleanup, service restart, log rotation config, system limits).
Label: `# File: fix_<incident_type>.yml`

### Terraform
A Terraform resource block that implements the infrastructure fix (increased limits,
auto-scaling group, resource quotas, instance type upgrade).
Label: `# File: fix_<incident_type>.tf`

### Kubernetes Manifest
The corrected Deployment, HorizontalPodAutoscaler, or ResourceQuota YAML manifest
that prevents recurrence at the platform level.
Label: `# File: fix_<incident_type>.yaml`

### Monitoring-as-Code (Prometheus Alert Rule)
A complete Prometheus alerting rule YAML (groups[].rules[]) that would have caught
this incident earlier. Include `for`, `labels.severity`, and `annotations.summary`.
Label: `# File: alert_<incident_type>.yml`

## Deployment Checklist
Numbered steps to apply each template safely in production.

Rules:
- All code blocks must be complete and runnable
- Use site-specific placeholders only where truly needed (e.g. CLUSTER_NAME, NAMESPACE)
- Base every template strictly on the retrieved context — do not invent resource names
- Cite the source runbook/incident at the end using [Source: filename] format
"""

# ── Runbook generation prompt ────────────────────────────────────
RUNBOOK_GEN_PROMPT = """You are a Senior Site Reliability Engineer and Technical Writer powered by IBM Bob.
Given a resolved incident conversation and the relevant context, generate a complete,
ready-to-use runbook Markdown document that can be saved to runbooks/ and indexed immediately.

Follow this exact structure:

# [ALERT_NAME] Runbook

## Overview
One paragraph: what this alert means, which service/system it affects, and why it matters.

## Severity & SLA
| Severity | Response Time | Escalation |
|---|---|---|
| P1 | Immediate | [from escalation policy in context] |
| P2 | 15 minutes | [from escalation policy in context] |

## Prerequisites
- Required tools and access needed before starting triage

## Immediate Actions (First 5 Minutes)
Numbered list of exact steps to stabilise the system.

## Diagnostic Commands
```bash
# All diagnostic commands as a single runnable bash block
```

## Root Cause Analysis
Step-by-step process to identify the root cause, derived from past incidents in context.

## Resolution Steps
Numbered list of resolution steps, from quickest to most invasive.

## Rollback Procedure
How to revert if the fix makes things worse.

## Escalation Criteria
Exact conditions under which to escalate, and to whom.

## Prevention & IaC Automation
- Monitoring rule that detects this condition early
- Infrastructure changes that prevent recurrence
- IaC templates to automate remediation

## Related Incidents
| Incident ID | Root Cause | Resolution |
|---|---|---|

## Sources
- [source files used]

Rules:
- Use ONLY information from the provided context and conversation
- Fill TBD for genuinely unknown fields — do not invent data
- The document must be self-contained and immediately actionable for a new engineer
"""

# ── Orchestration prompt ─────────────────────────────────────────
ORCHESTRATION_PROMPT = """You are an AI Incident Engineer powered by IBM Bob.
Your role is to act as an intelligent orchestrator — not just answering questions,
but producing a structured, step-by-step investigation and remediation workflow
that an engineer can follow or approve for automated execution.

Given the incident description and retrieved context, produce:

## Incident Classification
- Alert type, affected system, estimated severity (P1–P4), confidence level

## Investigation Workflow
A numbered, ordered sequence of investigation steps. For each step include:
- What to check and why
- The exact command to run (bash code block)
- Decision branch: `IF [condition] → THEN [next step] ELSE [alternate step]`

Example format:
```
Step 1 — Check service status
  Command: systemctl status <service>
  IF status=failed → proceed to Step 2 (check logs)
  IF status=running → proceed to Step 4 (check upstream)
```

## Automated Remediation Plan
Once root cause is identified, list the remediation actions in order:
1. Immediate fix (manual or scripted)
2. Verification step (how to confirm it worked)
3. IaC change to prevent recurrence

## Risk Assessment
- Risk of each remediation step (Low / Medium / High)
- Rollback plan if remediation makes things worse

## Success Criteria
Exact metrics or checks that confirm the incident is resolved.

Rules:
- Every command must come from the retrieved runbook context — no invented commands
- Use conditional branching — this is an investigation plan, not a flat list
- Be specific: use actual service names, paths, and thresholds from the context
- Cite sources at the end using [Source: filename] format
"""

REPORT_PROMPT = """You are an Infrastructure Incident Post-Mortem Writer.
Generate a complete, professional incident report in Markdown based on the triage conversation and context provided.

The report MUST include these exact sections:
# Incident Report — [Incident Title]

## Summary
2-3 sentence executive summary of what happened, impact, and resolution.

## Incident Details
| Field | Value |
|---|---|
| Severity | [P1/P2/P3] |
| Status | Resolved |
| Duration | [estimated] |
| Affected Services | [from context] |
| On-Call Engineer | [if known, else TBD] |
| Detection Time | [if known, else TBD] |
| Resolution Time | [if known, else TBD] |

## Timeline
Minute-by-minute timeline from detection to resolution based on the triage steps discussed.

## Root Cause Analysis
Primary root cause and contributing factors.

## Impact Assessment
User impact, service impact, revenue impact (estimate if unknown).

## Resolution Steps
Numbered list of exact steps taken.

## Lessons Learned
3-5 actionable lessons.

## Action Items
| Action | Owner | Due Date |
|---|---|---|
| [action] | [team] | [timeframe] |

## Prevention Measures
Steps taken or planned to prevent recurrence.

Rules:
- Use ONLY information from the provided context and conversation
- Fill in TBD for any unknown fields — do not invent data
- Keep it professional and concise
"""


def build_prompt(query: str, history: List[dict], context_chunks: List[dict]) -> str:
    context_text = ""
    for i, chunk in enumerate(context_chunks):
        context_text += f"\n--- Source {i+1}: {chunk['source']} (relevance: {chunk['score']:.2f}) ---\n"
        context_text += chunk["text"] + "\n"

    history_text = ""
    if history:
        history_text = "\n## Conversation History\n"
        for turn in history[-6:]:  # last 3 exchanges (6 messages)
            role = "Engineer" if turn["role"] == "user" else "Assistant"
            history_text += f"\n**{role}:** {turn['text']}\n"

    return f"""{SYSTEM_PROMPT}

## Retrieved Context
{context_text}
{history_text}
## Current Engineer Query
{query}

## Your Response
"""


# ── FastAPI app ─────────────────────────────────────────────────
app = FastAPI(title="Incident Triage Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


# ── Request/Response models ─────────────────────────────────────
class HistoryItem(BaseModel):
    role: str   # "user" or "assistant"
    text: str


class QueryRequest(BaseModel):
    query: str
    history: Optional[List[HistoryItem]] = []
    stream: Optional[bool] = False


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    chunks_used: int
    severity: str
    elapsed_ms: int


class ReportRequest(BaseModel):
    conversation: str
    query: str


class IaCRequest(BaseModel):
    query: str          # incident description / alert text
    conversation: str   # triage conversation so far


class RunbookGenRequest(BaseModel):
    query: str          # original alert that triggered the incident
    conversation: str   # full resolved triage conversation


class OrchestrationRequest(BaseModel):
    query: str
    history: Optional[List[HistoryItem]] = []


# ── Routes ──────────────────────────────────────────────────────
@app.get("/")
def root():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "Triage API running. POST /query to use."}


def _parse_retry_delay(error_str: str) -> str:
    """Extract a human-readable retry message from the quota error string."""
    import re
    m = re.search(r"retry in (\d+[\.\d]*)\s*s", error_str, re.IGNORECASE)
    if m:
        secs = float(m.group(1))
        return f"> Retry in **{secs:.0f} seconds**.\n\n"
    return ""


def _groq_generate(prompt: str) -> str:
    """Call Groq as a non-streaming fallback. Returns the answer text."""
    completion = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=2048,
    )
    return completion.choices[0].message.content


async def _groq_stream(prompt: str):
    """Yield text tokens from Groq as an async generator."""
    stream = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=2048,
        stream=True,
    )
    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token


@app.get("/health")
def health():
    backup = f"groq/{GROQ_MODEL}" if groq_client else "none"
    return {
        "status": "ok",
        "documents_indexed": len(set(c["source"] for c in CHUNKS)),
        "total_chunks": len(CHUNKS),
        "embedding_model": "all-MiniLM-L6-v2",
        "llm": GOOGLE_GEMINI_MODEL,
        "llm_backup": backup,
        "index_backend": "numpy+json (persistent)",
    }


@app.post("/query", response_model=QueryResponse)
def query_endpoint(req: QueryRequest):
    t0 = time.time()

    severity = detect_severity(req.query)
    chunks   = retrieve(req.query, CHUNKS, EMBEDDINGS, TOP_K)
    history  = [h.model_dump() for h in (req.history or [])]
    prompt   = build_prompt(req.query, history, chunks)

    try:
        response = gemini.generate_content(prompt)
        answer   = response.text
    except (ResourceExhausted, GoogleAPIError) as e:
        if groq_client:
            print(f"Gemini unavailable ({type(e).__name__}) — falling back to Groq.")
            try:
                answer = _groq_generate(prompt)
            except Exception as groq_err:
                answer = f"**Both LLMs unavailable.** Gemini error: {e} | Groq error: {groq_err}"
        else:
            retry_msg = _parse_retry_delay(str(e))
            answer = (
                f"**Gemini unavailable** ({type(e).__name__}).\n\n"
                f"{retry_msg}"
                f"**What to do:** Add a `GROQ_API_KEY` to your `.env` for automatic fallback, "
                f"or wait and try again."
            )

    sources  = list(dict.fromkeys(c["source"] for c in chunks))
    elapsed  = int((time.time() - t0) * 1000)

    return QueryResponse(
        answer=answer,
        sources=sources,
        chunks_used=len(chunks),
        severity=severity,
        elapsed_ms=elapsed,
    )


@app.post("/query/stream")
async def query_stream(req: QueryRequest):
    """Server-Sent Events streaming endpoint for word-by-word response."""
    t0 = time.time()
    severity = detect_severity(req.query)
    chunks   = retrieve(req.query, CHUNKS, EMBEDDINGS, TOP_K)
    history  = [h.model_dump() for h in (req.history or [])]
    prompt   = build_prompt(req.query, history, chunks)
    sources  = list(dict.fromkeys(c["source"] for c in chunks))

    async def event_generator():
        # First: send metadata
        meta = json.dumps({
            "type": "meta",
            "severity": severity,
            "sources": sources,
            "chunks_used": len(chunks),
        })
        yield f"data: {meta}\n\n"
        await asyncio.sleep(0)

        # Stream Gemini response; fall back to Groq on rate-limit
        full_text = ""
        try:
            response = gemini.generate_content(prompt, stream=True)
            for chunk_resp in response:
                if chunk_resp.text:
                    full_text += chunk_resp.text
                    payload = json.dumps({"type": "token", "text": chunk_resp.text})
                    yield f"data: {payload}\n\n"
                    await asyncio.sleep(0)
        except (ResourceExhausted, GoogleAPIError) as e:
            if groq_client:
                print(f"Gemini unavailable ({type(e).__name__}) — falling back to Groq (stream).")
                notice = "\n\n> ⚡ *Gemini unavailable — response via Groq backup.*\n\n"
                yield f"data: {json.dumps({'type': 'token', 'text': notice})}\n\n"
                try:
                    async for token in _groq_stream(prompt):
                        yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"
                        await asyncio.sleep(0)
                except Exception as groq_err:
                    yield f"data: {json.dumps({'type': 'error', 'text': f'Groq fallback failed: {groq_err}'})}\n\n"
                    return
            else:
                friendly = (
                    f"**Gemini unavailable** ({type(e).__name__}).\n\n"
                    f"**Tip:** Add a `GROQ_API_KEY` to your `.env` for automatic fallback."
                )
                yield f"data: {json.dumps({'type': 'token', 'text': friendly})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'elapsed_ms': int((time.time()-t0)*1000)})}\n\n"
            return
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
            return

        elapsed = int((time.time() - t0) * 1000)
        done = json.dumps({"type": "done", "elapsed_ms": elapsed})
        yield f"data: {done}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/report")
def generate_report(req: ReportRequest):
    chunks = retrieve(req.query, CHUNKS, EMBEDDINGS, TOP_K)
    context_text = "\n".join(c["text"] for c in chunks)

    prompt = f"""{REPORT_PROMPT}

## Triage Conversation
{req.conversation}

## Retrieved Context
{context_text}

## Generate the Incident Report
"""
    try:
        response = gemini.generate_content(prompt)
        return {"report": response.text}
    except (ResourceExhausted, GoogleAPIError) as e:
        if groq_client:
            print(f"Gemini unavailable ({type(e).__name__}) — falling back to Groq (/report).")
            try:
                return {"report": _groq_generate(prompt)}
            except Exception as groq_err:
                return {"report": f"**Both LLMs unavailable.** Gemini: {e} | Groq: {groq_err}"}
        retry_msg = _parse_retry_delay(str(e))
        return {"report": f"**Gemini unavailable** ({type(e).__name__}).\n\n{retry_msg}Wait a moment and try again."}


@app.post("/generate/iac")
def generate_iac(req: IaCRequest):
    """Generate IaC remediation templates (Terraform, K8s, Ansible, shell, Prometheus)."""
    chunks = retrieve(req.query, CHUNKS, EMBEDDINGS, TOP_K)
    context_text = "\n".join(
        f"--- Source: {c['source']} ---\n{c['text']}" for c in chunks
    )

    prompt = f"""{IAC_PROMPT}

## Incident Description
{req.query}

## Triage Conversation
{req.conversation}

## Retrieved Context
{context_text}

## Generate the IaC Templates
"""
    sources = list(dict.fromkeys(c["source"] for c in chunks))
    try:
        response = gemini.generate_content(prompt)
        return {"iac": response.text, "sources": sources}
    except (ResourceExhausted, GoogleAPIError) as e:
        if groq_client:
            print(f"Gemini unavailable ({type(e).__name__}) — falling back to Groq (/generate/iac).")
            try:
                return {"iac": _groq_generate(prompt), "sources": sources}
            except Exception as groq_err:
                return {"iac": f"**Both LLMs unavailable.** Gemini: {e} | Groq: {groq_err}", "sources": []}
        retry_msg = _parse_retry_delay(str(e))
        return {"iac": f"**Gemini unavailable** ({type(e).__name__}).\n\n{retry_msg}Wait a moment and try again.", "sources": []}


@app.post("/generate/runbook")
def generate_runbook(req: RunbookGenRequest):
    """Generate a complete runbook .md document from a resolved incident conversation."""
    chunks = retrieve(req.query, CHUNKS, EMBEDDINGS, TOP_K)
    context_text = "\n".join(
        f"--- Source: {c['source']} ---\n{c['text']}" for c in chunks
    )

    prompt = f"""{RUNBOOK_GEN_PROMPT}

## Original Incident Alert
{req.query}

## Resolved Triage Conversation
{req.conversation}

## Retrieved Context
{context_text}

## Generate the Runbook
"""
    try:
        response = gemini.generate_content(prompt)
        return {"runbook": response.text}
    except (ResourceExhausted, GoogleAPIError) as e:
        if groq_client:
            print(f"Gemini unavailable ({type(e).__name__}) — falling back to Groq (/generate/runbook).")
            try:
                return {"runbook": _groq_generate(prompt)}
            except Exception as groq_err:
                return {"runbook": f"**Both LLMs unavailable.** Gemini: {e} | Groq: {groq_err}"}
        retry_msg = _parse_retry_delay(str(e))
        return {"runbook": f"**Gemini unavailable** ({type(e).__name__}).\n\n{retry_msg}Wait a moment and try again."}


@app.post("/orchestrate")
def orchestrate(req: OrchestrationRequest):
    """Generate a structured, branching investigation + remediation workflow."""
    chunks = retrieve(req.query, CHUNKS, EMBEDDINGS, TOP_K)
    context_text = "\n".join(
        f"--- Source: {c['source']} ---\n{c['text']}" for c in chunks
    )
    history = [h.model_dump() for h in (req.history or [])]
    history_text = ""
    if history:
        history_text = "\n## Conversation History\n"
        for turn in history[-6:]:
            role = "Engineer" if turn["role"] == "user" else "Assistant"
            history_text += f"\n**{role}:** {turn['text']}\n"

    prompt = f"""{ORCHESTRATION_PROMPT}

## Incident Description
{req.query}
{history_text}
## Retrieved Context
{context_text}

## Generate the Investigation Workflow
"""
    sources = list(dict.fromkeys(c["source"] for c in chunks))
    severity = detect_severity(req.query)
    try:
        response = gemini.generate_content(prompt)
        return {"workflow": response.text, "sources": sources, "severity": severity}
    except (ResourceExhausted, GoogleAPIError) as e:
        if groq_client:
            print(f"Gemini unavailable ({type(e).__name__}) — falling back to Groq (/orchestrate).")
            try:
                return {"workflow": _groq_generate(prompt), "sources": sources, "severity": severity}
            except Exception as groq_err:
                return {"workflow": f"**Both LLMs unavailable.** Gemini: {e} | Groq: {groq_err}", "sources": [], "severity": "UNKNOWN"}
        retry_msg = _parse_retry_delay(str(e))
        return {"workflow": f"**Gemini unavailable** ({type(e).__name__}).\n\n{retry_msg}Wait a moment and try again.", "sources": [], "severity": "UNKNOWN"}


@app.post("/upload")
async def upload_document(file: UploadFile = File(...), folder: str = Form("runbooks")):
    global CHUNKS, EMBEDDINGS

    if not file.filename.endswith((".md", ".txt")):
        return {"error": "Only .md and .txt files are supported"}

    if folder not in ("runbooks", "incidents", "docs"):
        return {"error": "folder must be one of: runbooks, incidents, docs"}

    content = await file.read()

    # Upload to S3 if configured, otherwise write to local disk
    if os.getenv("S3_BUCKET_NAME"):
        try:
            s3_key = s3_upload_document(file.filename, content, folder=folder)
            print(f"Uploaded to S3: {s3_key}")
        except Exception as e:
            return {"error": f"S3 upload failed: {e}"}
    else:
        upload_dir = os.path.join(BASE_DIR, folder)
        os.makedirs(upload_dir, exist_ok=True)
        save_path  = os.path.join(upload_dir, file.filename)
        with open(save_path, "wb") as f:
            f.write(content)

    print(f"Re-indexing after upload of {file.filename}...")
    # Delete persisted index so build_index forces a rebuild
    from vector_store import FINGERPRINT_FILE
    if os.path.exists(FINGERPRINT_FILE):
        os.remove(FINGERPRINT_FILE)

    CHUNKS, EMBEDDINGS = build_index(BASE_DIR)
    print("Re-index complete.")

    return {
        "message": f"{file.filename} uploaded and indexed successfully",
        "total_chunks": len(CHUNKS),
        "total_documents": len(set(c["source"] for c in CHUNKS)),
    }


@app.get("/documents")
def list_documents():
    sources = {}
    for chunk in CHUNKS:
        src = chunk["source"]
        if src not in sources:
            sources[src] = {"source": src, "folder": chunk["folder"], "chunks": 0}
        sources[src]["chunks"] += 1
    return {"documents": list(sources.values()), "total": len(sources)}
