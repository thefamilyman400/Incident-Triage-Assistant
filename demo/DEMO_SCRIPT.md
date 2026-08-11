# Demo Script — AI Incident Engineer
### IBM WatsonX Challenge — Use Case 2

**Total demo time:** 10–12 minutes
**URL:** http://localhost:8080

---

## Before the Demo

- Server running: `python -m uvicorn main:app --port 8080`
- Browser open at http://localhost:8080
- Confirm header shows: `11 docs · 315 chunks · gemini-2.0-flash`
- Sidebar shows green pulse dot (API reachable)
- **Streaming toggle is ON** (checkbox in header, checked)
- Welcome screen shows 6 scenario cards: HIGH CPU · SERVICE DOWN · **GENERATE IaC FIX** · **PLAN INVESTIGATION** · DISK SPACE · HISTORY

---

## Opening (30 seconds)

> "I'm going to show you an AI Incident Engineer — not just a chatbot that answers questions,
> but a system that triages the alert, plans the investigation, generates the Infrastructure-as-Code
> to fix it permanently, writes the runbook, and indexes it for the next engineer — all in under
> 2 minutes. Let me show you."

---

## Demo 1 — High CPU Alert (2 minutes)

Click the **"HIGH CPU"** scenario card on the welcome screen, or type:

> `CPU usage on prod-db-01 is at 98% for the last 12 minutes`

**Point out while streaming:**
- The answer starts arriving **word-by-word** immediately — no waiting
- The **orange P2 banner** appears at the top before text starts
- The response is structured: Immediate Actions → Diagnostic Commands → Root Causes → Past Incidents → Escalation

**Point out after completion:**
- **Source chips** at the bottom — every claim is cited to a real document
- **Response time badge** — e.g. "2.4s" in green — *"That's 2 seconds vs 45 minutes"*
- **Copy button** on the bash code block — hover to reveal it, click it

---

## Demo 2 — P1 Service Down (2 minutes)

Click **"SERVICE DOWN"** card or type:

> `Payment service health check has been failing for 5 minutes with 503 errors`

**Point out:**
- **Red P1 banner** — highest severity, different visual urgency than P2
- Rollback procedure appears — actual `kubectl` commands, ready to copy
- INC-3601 referenced — *"It found a past incident where this exact thing happened, including the root cause"*
- Escalation path clearly stated — who to call, which Slack channel

---

## Demo 3 — Conversation Memory Follow-up (1.5 minutes)

After Demo 2, type:

> `How was INC-3601 resolved?`

Then:

> `Who was responsible for the fix?`

**Point out:**
- No need to repeat context — the assistant **remembers the conversation**
- This is multi-turn — works like a real conversation, not isolated queries

---

## Demo 4 — Incident Report Generation (1.5 minutes)

After the service down response, click **"Generate Report"** in the sources bar.

Wait for the modal to populate, then:

**Point out:**
- Full post-mortem in seconds: Summary → Timeline → Root Cause → Impact → Action Items
- **Copy Report** button — paste directly into Confluence or Jira
- *"Writing this manually after an incident takes 30–45 minutes. This takes 10 seconds."*

---

## Demo 5 — Live Document Upload (1 minute)

Drag any `.md` file onto the **Upload Zone** in the sidebar (or prepare a dummy runbook).

**Point out:**
- *"Engineers can add their own runbooks — no restart needed"*
- Status updates live: `file.md indexed`
- Doc count in header increments
- Immediately queryable

---

## Demo 6 — IaC Generation (2 minutes)

After the service-down triage response, click **Generate Fix** in the sources bar.

**Point out while modal loads:**
- *"Bob is now generating Infrastructure-as-Code — not just explaining the fix, but producing it"*

**Point out after completion:**
- **Shell script** at the top — copy and run immediately as first response
- **Ansible playbook** — run the same fix across 50 servers simultaneously, not just one
- **Terraform block** — permanent infrastructure change, ready to commit to Git
- **Prometheus alert rule** — the monitoring gap that let this incident happen is now closed
- **Deployment Checklist** at the bottom — numbered steps to apply each template safely
- *"Every template is grounded in the runbook context — no invented resource names"*

---

## Demo 7 — Plan Investigation (1.5 minutes)

Click the **PLAN INVESTIGATION** welcome card (or click **Plan Investigation** from the sources bar).

**Point out:**
- **Incident Classification** at top — severity, confidence level, affected system
- **Branching workflow** — `IF status=failed → Step 2`, `ELSE → Step 4`
- *"This is agentic reasoning — Bob isn't just answering, it's thinking through the decision tree"*
- **Automated Remediation Plan** — ordered fix steps with verification
- **Risk Assessment** — each step rated Low/Medium/High risk before you touch anything

---

## Demo 8 — Save as Runbook (1 minute)

After the triage conversation, click **Generate Report** then click **Save as Runbook**.

**Point out:**
- Button text changes: *"Generating..."* → *"Saved!"*
- Doc count in header increments (e.g. `11 docs` → `12 docs`)
- Info message confirms: *"GENERATED_RUNBOOK_... indexed"*
- *"That incident just taught the system. The next engineer who hits this alert gets this runbook."*
- *"No one had to manually write documentation. Bob did it automatically."*

---

## Closing (30 seconds)

> "What you just saw: a P1 production alert triaged in seconds, with exact runbook steps,
> a branching investigation plan, copy-ready Terraform and Ansible, a Prometheus alert rule
> to prevent recurrence, a post-mortem, and a new runbook automatically added to the knowledge base —
> all grounded in your actual documentation, all cited.
>
> The impact: MTTR drops from 45 minutes to under 5. Every incident makes the system smarter.
> Senior engineers stop being interrupted. New engineers are productive in days.
>
> This is IBM Bob as an AI Incident Engineer — triage, automate, document, learn."

---

## Key Numbers to Mention

| Metric | Before | After |
|---|---|---|
| Time to first triage action | 30–45 min | < 30 seconds |
| Runbook retrieval | 15–20 min | < 2 seconds |
| IaC template generation | Manual (hours) | < 15 seconds |
| Investigation plan creation | Senior engineer (30 min) | < 10 seconds |
| Incident report writing | 30–45 min | < 10 seconds |
| New runbook creation | Manual (1–2 hrs) | Automatic, 0 effort |
| Server startup (after first run) | — | < 5 seconds |
| Documents indexed | 11 | Self-expanding |

---

## Backup Queries (if asked)

```
"What are the immediate steps for a disk space critical alert?"
→ DISK_SPACE_RUNBOOK · INC-3455 · du/df commands · cleanup steps

"Show me past incidents related to connection pool exhaustion"
→ INC-3301 · root cause: connection leak · fix: pool size increase

"What is the rollback procedure for a bad Kubernetes deployment?"
→ kubectl rollout undo · SERVICE_DOWN_RUNBOOK · INC-3601

"Who do I escalate a P1 incident to?"
→ ESCALATION_POLICY.md · on-call SRE → manager → VP path
```
