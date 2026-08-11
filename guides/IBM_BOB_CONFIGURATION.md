# IBM Bob Configuration Guide
## Incident Triage Assistant — IBM WatsonX Challenge Demo

---

## Overview

This guide walks through configuring IBM Bob as an **AI Incident Engineer** persona.
Bob acts as the conversational and orchestration front-end; ICA Context Studio
(configured separately) supplies the grounded knowledge. Complete the
[ICA Context Studio Setup](./ICA_CONTEXT_STUDIO_SETUP.md) before this guide.

Bob's role has been extended beyond simple Q&A. It now:
1. **Triages** incidents with grounded runbook retrieval
2. **Plans** structured investigation workflows with conditional branching
3. **Generates** IaC remediation templates (Terraform, K8s, Ansible, Prometheus)
4. **Authors** new runbooks from resolved incidents and indexes them automatically
5. **Recommends** proactive infrastructure improvements after every response

---

## System Prompt / Persona Configuration

Copy the prompt below **exactly** into the system prompt field.

```
You are an AI Incident Engineer powered by IBM Bob. Your role is to help on-call
engineers quickly diagnose, remediate, and prevent infrastructure incidents.

When given an alert or incident description you MUST:

(1) Identify the most relevant runbook and list its IMMEDIATE ACTIONS step by step
(2) Show the most relevant DIAGNOSTIC COMMANDS from the runbook (as code blocks)
(3) List PROBABLE ROOT CAUSES based on the runbook and past incidents
(4) Reference PAST SIMILAR INCIDENTS from context (ID, severity, root cause, resolution)
(5) State ESCALATION criteria and path (who to contact, when, which Slack channel)
(6) Suggest 2-3 PROACTIVE IMPROVEMENTS — monitoring gaps, IaC automation opportunities,
    or hardening steps — grounded strictly in the retrieved context

Always cite your sources at the end using [Source: filename] format.
Be concise and actionable — engineers are under pressure.
Never make up incident IDs, runbook steps, or commands not present in the context.
```

**Why this prompt works:**
- The 6-point instruction list makes Bob an *orchestrator*, not just a Q&A system
- Point 6 (Proactive Improvements) directly addresses the IaC and automation goals
- The citation rule reinforces RAG grounding from Context Studio
- The closing sentence sets tone — no preamble, just actions

---

## How to Set the System Prompt in IBM Bob

1. Open your IBM Bob instance → **Configure → Persona & Behaviour**
2. Clear any existing default text in the **System Prompt** field
3. Paste the system prompt from the section above
4. Set **Temperature** to `0.2` — keeps triage responses deterministic
5. Set **Max output tokens** to `1200` — increased from 800 to accommodate IaC templates
6. Click **Save Persona**

---

## MCP Tool Registration

Register the following tools so Bob can orchestrate the full incident lifecycle via MCP.
Each tool maps to an endpoint in the FastAPI backend.

| Tool Name | Method | Endpoint | Description |
|---|---|---|---|
| `triage_incident` | POST | `/query/stream` | Triage an alert — returns runbook steps, diagnostics, escalation |
| `plan_investigation` | POST | `/orchestrate` | Generate a branching investigation workflow |
| `generate_iac` | POST | `/generate/iac` | Generate Terraform, K8s, Ansible, shell, and Prometheus templates |
| `generate_runbook` | POST | `/generate/runbook` | Auto-author a new runbook from a resolved incident |
| `generate_report` | POST | `/report` | Generate a full incident post-mortem |
| `list_knowledge` | GET | `/documents` | List all indexed documents in the knowledge base |
| `upload_document` | POST | `/upload` | Add a new runbook or policy document to the knowledge base |

### Tool Payload Schemas

**triage_incident / plan_investigation**
```json
{ "query": "alert description", "history": [{"role": "user", "text": "..."}] }
```

**generate_iac / generate_runbook / generate_report**
```json
{ "query": "original alert text", "conversation": "full triage conversation text" }
```

---

## Suggested Starter Questions (Quick Prompts Panel)

Configure these in **Configure → Quick Prompts**.

| Button Label | Prompt Text |
|---|---|
| HIGH CPU Alert | `CPU usage is above 90% on host app-prod-02. What should I do right now?` |
| Disk Space Alert | `Disk usage on /var/log is at 95% on db-prod-01. Walk me through remediation.` |
| Service Down | `The checkout service is returning 503 after the 14:30 deployment. Immediate steps?` |
| Plan Investigation | `CPU usage on prod-db-01 is at 98%. Build me a step-by-step investigation workflow.` |
| Generate IaC Fix | `Generate Terraform and Ansible templates to fix and prevent the CPU spike on prod-db-01.` |
| Generate Runbook | `Write a complete runbook for high CPU alerts based on the incidents we just resolved.` |
| Escalation Check | `This incident has been ongoing for 45 minutes. Should I escalate, and to whom?` |

---

## Response Format Guidance

### Standard Triage Response
```
## Immediate Actions
1. [Step from runbook]
2. [Step from runbook]

## Diagnostic Commands
```bash
[commands from runbook]
```

## Probable Root Causes
- [from runbook context]

## Past Similar Incidents
- INC-XXXX: [summary, root cause, resolution]

## Escalation
[Escalate / Do not escalate] — [reason from policy]

## Proactive Improvements
- [monitoring gap or IaC opportunity from context]

[Source: RUNBOOK_NAME.md, INC-XXXX.md]
```

### Investigation Workflow Response
```
## Incident Classification
- Type: [CPU/Disk/Network/Service], Severity: P[1-4]

## Investigation Workflow
Step 1 — [What to check]
  Command: [exact bash command]
  IF [condition] → Step 2
  ELSE → Step 4

## Automated Remediation Plan
1. [Immediate fix]
2. [Verification step]
3. [IaC change to prevent recurrence]

## Risk Assessment + Success Criteria
```

### IaC Template Response
```
## IaC Remediation Templates

### Shell Automation Script
# File: triage_high_cpu.sh
```bash
[complete script]
```

### Ansible Playbook
# File: fix_high_cpu.yml
```yaml
[complete play]
```

### Terraform
# File: fix_high_cpu.tf
```hcl
[resource block]
```

### Kubernetes Manifest / Prometheus Rule
[YAML blocks]

## Deployment Checklist
1. [Steps to apply safely]
```

---

## Testing Checklist

Run through all items before the WatsonX Challenge demo presentation.

- [ ] System prompt saved, temperature `0.2`, max tokens `1200`
- [ ] Context Studio connection shows **Connected** (green badge)
- [ ] All 7 MCP tools registered and show **Active** status
- [ ] HIGH CPU quick prompt returns runbook steps + proactive improvements
- [ ] **Plan Investigation** prompt returns a branching workflow with IF/ELSE steps
- [ ] **Generate IaC Fix** prompt returns at least shell script + Ansible + Prometheus rule
- [ ] **Generate Runbook** prompt returns a complete `.md` runbook structure
- [ ] Every response includes at least one **[Source: filename]** citation
- [ ] No response invents a runbook, incident ID, or command not in the knowledge base
- [ ] Responses are under 1200 tokens (no truncation mid-template)
