# ICA Context Studio Setup Guide
## Incident Triage Assistant — IBM WatsonX Challenge Demo

---

## What is ICA Context Studio?

ICA (IBM Consulting Advantage) Context Studio is a managed RAG (Retrieval-Augmented Generation)
platform that allows teams to build and deploy grounded AI assistants without writing infrastructure
code. It provides a no-code interface for defining a schema, uploading documents as a data source,
and exposing the knowledge base to IBM Bob via MCP (Model Context Protocol). For the Incident
Triage Assistant, Context Studio serves as the retrieval layer — ingesting runbooks, past incident
reports, and reference documentation so that IBM Bob can cite specific, verified sources rather than
generating generic troubleshooting advice.

---

## Pre-requisites

- Active IBM Consulting Advantage (ICA) tenant with **Context Studio** feature enabled
- IBM w3 ID with at least **Editor** role on the target ICA workspace
- IBM Bob instance provisioned and linked to the same ICA workspace
- All source documents available locally (see Step 3)
- Supported browsers: Chrome 120+ or Edge 120+ (Safari not recommended for file upload)

---

## The 4-Step Flow

```
1. Schema  →  2. Context  →  3. Source & Data  →  4. Expose via MCP
```

---

## Step 1: Create Schema

The Schema defines the structure of the knowledge base — what fields each document will have.

1. Log in to ICA and navigate to **Context Studio** from the left-hand navigation panel.
2. Click **Create Schema**.
3. Fill in the schema details:

   | Field           | Value                                          |
   |-----------------|------------------------------------------------|
   | **Schema Name** | `IncidentTriageSchema`                         |
   | **Description** | `Schema for infrastructure runbooks, incident post-mortems, escalation policies and alert definitions used by the Incident Triage Assistant.` |

4. Add the following fields to the schema:

   | Field Name      | Type     | Description                                  |
   |-----------------|----------|----------------------------------------------|
   | `title`         | String   | Document or runbook title                    |
   | `content`       | String   | Full document body (main text field for RAG) |
   | `doc_type`      | String   | One of: `runbook`, `incident`, `policy`, `alert` |
   | `severity`      | String   | Alert severity or incident priority (P1–P4)  |
   | `source_file`   | String   | Original filename for citation               |

5. Click **Save Schema** / **Create**.

> **Tip:** The `content` field is the one Context Studio will embed and search against. Make sure it
> is mapped correctly in Step 3.

---

## Step 2: Create Context

The Context ties the schema to a named knowledge base that IBM Bob will query.

1. After saving the schema, navigate to the **Context** section (or click **+ New Context**).
2. Fill in the context details:

   | Field           | Value                                          |
   |-----------------|------------------------------------------------|
   | **Context Name**| `Incident Triage Assistant`                    |
   | **Description** | `Knowledge base for on-call infrastructure engineers. Contains runbooks, past incident reports, escalation policy, and alert definitions.` |
   | **Schema**      | Select `IncidentTriageSchema` (created in Step 1) |

3. Click **Create Context**.

> This context is what IBM Bob will be pointed at in Step 4. The name here will appear in Bob's
> MCP connection configuration.

---

## Step 3: Add Source & Data

This is where you upload all the runbook and incident documents.

1. Inside your context, click **Source & Data** (or **+ Add Data Source**).
2. Select **File Upload** as the source type.
3. Upload the following files in batches by document type:

### Batch 1 — Runbooks (4 files)
| File                                    | `doc_type` value |
|-----------------------------------------|------------------|
| `runbooks/HIGH_CPU_RUNBOOK.md`          | `runbook`        |
| `runbooks/DISK_SPACE_RUNBOOK.md`        | `runbook`        |
| `runbooks/SERVICE_DOWN_RUNBOOK.md`      | `runbook`        |
| `runbooks/NETWORK_LATENCY_RUNBOOK.md`   | `runbook`        |

### Batch 2 — Incident Post-Mortems (5 files)
| File                                            | `doc_type` value |
|-------------------------------------------------|------------------|
| `incidents/INC-2847-HIGH-CPU-BATCH-JOB.md`     | `incident`       |
| `incidents/INC-3012-CPU-MISSING-INDEX.md`       | `incident`       |
| `incidents/INC-3301-CONNECTION-POOL-EXHAUSTION.md` | `incident`    |
| `incidents/INC-3455-DISK-FULL-LOGS.md`         | `incident`       |
| `incidents/INC-3601-SERVICE-DOWN-BAD-DEPLOY.md`| `incident`       |

### Batch 3 — Policy & Reference Docs (2 files)
| File                          | `doc_type` value |
|-------------------------------|------------------|
| `docs/ESCALATION_POLICY.md`   | `policy`         |
| `docs/ALERT_DEFINITIONS.md`   | `alert`          |

4. For each file, map the fields:
   - **content** → map to the document body (full text)
   - **title** → map to document filename or first heading
   - **source_file** → set to the filename (e.g. `HIGH_CPU_RUNBOOK.md`)
   - **doc_type** → set manually per batch (see table above)

5. Click **Save** / **Ingest**. Wait for all 11 files to show status **Indexed** ✅ before proceeding.

> **If a file fails to index:** Re-save the `.md` file as UTF-8 encoding and re-upload.

---

## Step 4: Expose via MCP

This step makes the Context Studio knowledge base available to IBM Bob via the
Model Context Protocol (MCP).

1. Inside your context, click **Expose via MCP**.
2. You will see an MCP endpoint configuration screen. Fill in:

   | Field               | Value                                     |
   |---------------------|-------------------------------------------|
   | **Endpoint Name**   | `incident-triage-mcp`                     |
   | **Access**          | Restricted to your IBM Bob instance       |
   | **Search Field**    | `content`                                 |
   | **Return Fields**   | `title`, `content`, `doc_type`, `source_file`, `severity` |
   | **Top-K results**   | `5`                                       |

3. Click **Generate MCP Endpoint** / **Expose**.
4. Copy the **MCP Endpoint URL** and **API Key** — you will need both when configuring IBM Bob
   (see [`IBM_BOB_CONFIGURATION.md`](./IBM_BOB_CONFIGURATION.md)).

5. The context card should now show a green **MCP Active** or **Exposed** badge.

---

## Testing the Setup

Before connecting to Bob, verify retrieval is working from the Context Studio **Test** panel:

| Test Query                                       | Expected Result                              |
|--------------------------------------------------|----------------------------------------------|
| `"CPU usage above 90% on app server"`            | `HIGH_CPU_RUNBOOK` + `INC-2847` chunks       |
| `"disk full on /var/log"`                        | `DISK_SPACE_RUNBOOK` + `INC-3455` chunks     |
| `"service returning 503 after deployment"`       | `SERVICE_DOWN_RUNBOOK` + `INC-3601` chunks   |
| `"connection pool exhausted"`                    | `INC-3301` chunk                             |
| `"who do I escalate a P1 incident to"`           | `ESCALATION_POLICY` chunk                    |

For each query, verify that **source filenames are visible** in the results.
If a query returns zero results, check that the `content` field mapping is correct in Step 3.

---

## Common Issues and Fixes

| Symptom                          | Likely Cause                        | Fix                                                   |
|----------------------------------|-------------------------------------|-------------------------------------------------------|
| File stuck at "Processing"       | Large file or encoding issue        | Re-save as UTF-8, split files > 500 lines, re-upload  |
| Retrieval returns 0 results      | Wrong field mapped as search field  | Confirm `content` is set as the search field in MCP   |
| Wrong document returned          | `doc_type` not mapped               | Tag files correctly and re-ingest                     |
| MCP endpoint not reachable       | API key not copied correctly        | Regenerate the key from the Expose via MCP screen     |
| Bob ignores retrieved context    | System prompt conflict              | Ensure Bob system prompt says to use provided context |
| Citations missing in Bob answers | Return fields misconfigured         | Add `source_file` and `title` to Return Fields in MCP |
