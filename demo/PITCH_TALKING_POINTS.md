# Pitch Talking Points — AI Incident Engineer
### IBM WatsonX Challenge — Use Case 2

---

## The One-Sentence Pitch

> "An AI Incident Engineer powered by IBM Bob that triages production alerts, plans the investigation with conditional branching, generates Infrastructure-as-Code remediation templates, and automatically writes and indexes new runbooks — all grounded in your actual documentation."

---

## The Problem (30 seconds)

- Every infrastructure team has runbooks, post-mortems, and policies — scattered across Confluence, Jira, PagerDuty, SharePoint, email threads
- When an alert fires at 2 AM, engineers spend **30–45 minutes just gathering context** before they can start diagnosing
- This is the **context-gathering tax** — and it happens on every single incident, every time, for every engineer

**Three root causes:**
1. Documentation is scattered across multiple tools
2. Operational knowledge lives in senior engineers' heads
3. New engineers take weeks to build up enough context to triage independently

---

## The Solution (1 minute)

IBM Bob as an AI Incident Engineer that:

1. **Triages** — retrieves the exact runbook and past incidents for any alert in < 3 seconds
2. **Plans** — generates a branching investigation workflow (IF/ELSE decision tree) powered by Bob's reasoning
3. **Automates** — produces IaC templates: shell script, Ansible playbook, Terraform, K8s manifest, Prometheus alert rule
4. **Documents** — generates a full post-mortem report in 10 seconds
5. **Learns** — converts every resolved incident into a new indexed runbook automatically
6. **Cites** — every claim grounded in retrieved documents, no hallucination

---

## Why RAG (not a chatbot)?

| Generic chatbot | This assistant |
|---|---|
| Makes up runbook steps | Only uses steps from your actual runbooks |
| No incident history | Surfaces INC-XXXX with root cause + resolution |
| No citations | Every answer cites the exact source document |
| Stale training data | Instant update — add a runbook, it's indexed immediately |

---

## IBM Bob as Orchestrator (Not Just a Chatbot)

This is the critical distinction the challenge judges are looking for:

| Passive RAG Chatbot | IBM Bob as AI Incident Engineer |
|---|---|
| Answers questions about alerts | Plans a branching investigation workflow |
| Explains how to fix incidents | Generates the IaC to fix it |
| Engineers write runbooks manually | Bob auto-authors runbooks from resolved incidents |
| Knowledge base is static | Knowledge base grows with every incident |
| Describes remediation steps | Produces Ansible/Terraform/K8s ready to apply |

---

## Technical Differentiators

**Persistent vector index** — First run embeds documents (30–60s). Every subsequent restart loads from disk in **< 200ms**. The server is ready in seconds.

**Streaming via SSE** — Response streams token-by-token. Engineers see answers forming in real time, not a loading spinner followed by a wall of text.

**Conversation memory** — The last 3 exchanges are sent with every query. "What about the disk version of that?" resolves correctly.

**Zero dependencies on external vector DBs** — Pure NumPy + JSON persistence. Works on any machine, any OS, no Docker, no database.

**Graceful rate limit handling** — If the Gemini quota is hit, a friendly message with retry countdown appears in the chat instead of a 500 error.

---

## IBM Bob Alignment

| IBM Bob Principle | How this app implements it |
|---|---|
| Grounded responses | Every answer uses only retrieved document chunks — no LLM training data |
| Cited answers | Source chips on every response link back to the exact document |
| Actionable output | Triage → workflow → IaC templates → post-mortem → new runbook |
| Contextual awareness | Conversation history injected into every prompt |
| Orchestration | 5 specialised prompts; Bob chooses depth based on what is asked |
| IaC generation | Produces Terraform, K8s, Ansible, shell, Prometheus from incident context |
| Continuous learning | Every resolved incident → new runbook → indexed → benefits next engineer |

---

## Business Impact

| KPI | Before | After |
|---|---|---|
| MTTR (Mean Time to Resolution) | 45–90 min | 15–30 min |
| Time to first triage action | 30–45 min | < 30 seconds |
| IaC remediation template creation | Hours (manual) | < 15 seconds |
| Investigation planning | Senior engineer, 30 min | < 10 seconds |
| Senior engineer interruptions per incident | 2–3 | 0–1 |
| New engineer onboarding to independent triage | 3–4 weeks | 3–5 days |
| Post-mortem writing time | 30–45 min | < 10 seconds |
| New runbook creation after incident | 1–2 hours (manual) | Automatic, 0 effort |
| Knowledge base growth | Manual, irregular | Self-expanding after every incident |

---

## Scalability

- Drop any `.md` or `.txt` file in the relevant folder — it's indexed on next restart
- Or drag-and-drop via the UI Upload Zone — live re-index, no restart needed
- PDF/Word support is the natural next step (`pymupdf`, `python-docx`)
- Swap Gemini for IBM watsonx.ai Granite for fully on-premise deployment

---

## Common Questions

**"Does this send our runbooks to Google?"**
> Only the top-6 most relevant *chunks* (not full documents) are sent to Gemini per query. The embedding model runs entirely locally — documents never leave your machine for indexing.

**"What if we have hundreds of runbooks?"**
> The NumPy index scales to ~50,000 chunks with sub-5ms retrieval. For larger deployments, the vector_store.py module can be swapped for a proper vector DB with zero changes to the rest of the app.

**"Can we use IBM watsonx.ai instead of Gemini?"**
> Yes — the LLM call is a single function. Replace `genai.GenerativeModel` with the watsonx.ai `ModelInference` client and the rest of the app is unchanged.

**"How do we keep it up to date?"**
> Drop new runbooks in the folder and restart (auto-detects changes via fingerprint), or use the Upload Zone in the UI for zero-downtime updates.
