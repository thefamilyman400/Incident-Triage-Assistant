# ICA Context Studio — Schema Builder Step-by-Step Guide
## How to populate Nodes, Edges, Actions and Constraints

---

## FASTEST PATH — Upload Sample Data (Recommended)

Looking at your Schema Builder screen, the quickest way to populate everything is:

1. Click **Upload Sample Data ↑** (top right button in the Schema Builder)
2. Upload the file: `schema/sample_data.json`
3. ICA will auto-detect node types from the `nodeType` field and generate:
   - All 5 node types (Incident, Resolution, KnowledgeArticle, System, EscalationPath)
   - All properties per node from the JSON fields
   - Suggested relationships from the reference fields (resolvedBy, guidedBy, triggeredBy etc.)
4. Review the generated schema and confirm
5. Then manually add Constraints (see Section 4 below)

---

## MANUAL PATH — Add each section yourself

If Upload Sample Data does not auto-generate what you need, follow these steps manually.

---

## SECTION 1 — NODES (Click "Add Node +")

For each node below, click **Add Node +** and fill in the form.

---

### NODE 1: Incident

| Field | Value |
|---|---|
| **Node Name** | `Incident` |
| **Description** | `A production infrastructure event requiring active triage and resolution` |

**Properties to add:**

| Property Name | Type | Required | Notes |
|---|---|---|---|
| `incident_id` | String | ✅ Yes | Pattern: INC-XXXX (e.g. INC-2847) |
| `title` | String | ✅ Yes | Short incident title |
| `content` | String | ✅ Yes | Full post-mortem body — mark as **Embedding Field** |
| `severity` | String | ✅ Yes | Allowed values: P1, P2, P3, P4 |
| `status` | String | ✅ Yes | Allowed values: open, in-progress, resolved, monitoring |
| `source_file` | String | ✅ Yes | e.g. INC-2847-HIGH-CPU-BATCH-JOB.md |
| `affected_services` | String List | ✅ Yes | e.g. ["Payment Service", "prod-db-01"] |
| `on_call_engineer` | String | ✅ Yes | e.g. Sarah Mitchell |
| `incident_commander` | String | No | e.g. David Okafor |
| `duration_minutes` | Integer | No | Minimum: 0 |
| `created_at` | DateTime | ✅ Yes | ISO 8601 |
| `resolved_at` | DateTime | No | ISO 8601 |
| `tags` | String List | No | e.g. cpu, database, postgres |

---

### NODE 2: Resolution

| Field | Value |
|---|---|
| **Node Name** | `Resolution` |
| **Description** | `Root cause, fix steps and follow-up actions for a closed incident` |

**Properties to add:**

| Property Name | Type | Required | Notes |
|---|---|---|---|
| `resolution_id` | String | ✅ Yes | Pattern: RES-XXXX (e.g. RES-2847) |
| `incident_id` | String | ✅ Yes | Foreign key to Incident node |
| `root_cause` | String | ✅ Yes | Minimum 50 characters |
| `resolution_steps` | String List | ✅ Yes | Ordered list of steps taken |
| `action_items` | String List | No | Jira ticket references |
| `lessons_learned` | String | No | Key learnings |
| `resolved_by` | String | ✅ Yes | e.g. Sarah Mitchell |
| `resolved_at` | DateTime | ✅ Yes | ISO 8601 |
| `duration_minutes` | Integer | ✅ Yes | Minimum: 0 |
| `prevention_measures` | String List | No | Controls implemented |

---

### NODE 3: KnowledgeArticle

| Field | Value |
|---|---|
| **Node Name** | `KnowledgeArticle` |
| **Description** | `Runbooks, alert definitions, and escalation policies — the RAG knowledge base` |

**Properties to add:**

| Property Name | Type | Required | Notes |
|---|---|---|---|
| `title` | String | ✅ Yes | e.g. HIGH_CPU_RUNBOOK |
| `content` | String | ✅ Yes | Full article body — mark as **Embedding Field** |
| `article_type` | String | ✅ Yes | Allowed values: runbook, policy, alert |
| `source_file` | String | ✅ Yes | e.g. HIGH_CPU_RUNBOOK.md |
| `version` | String | No | e.g. 3.1 |
| `owning_team` | String | ✅ Yes | e.g. Platform Operations, Infra SRE |
| `severity_coverage` | String List | No | e.g. P1, P2 |
| `diagnostic_commands` | String List | No | Shell/SQL commands |
| `escalation_criteria` | String List | No | When to escalate |
| `tags` | String List | No | e.g. cpu, database |
| `updated_at` | DateTime | No | Used for staleness check |

---

### NODE 4: System

| Field | Value |
|---|---|
| **Node Name** | `System` |
| **Description** | `A named infrastructure service, server, or platform component` |

**Properties to add:**

| Property Name | Type | Required | Notes |
|---|---|---|---|
| `system_id` | String | ✅ Yes | e.g. prod-db-01 |
| `display_name` | String | ✅ Yes | e.g. Primary Production Database |
| `system_type` | String | ✅ Yes | Allowed values: database, application, platform, network, queue, other |
| `environment` | String | ✅ Yes | Allowed values: production, staging, development |
| `owning_team` | String | ✅ Yes | e.g. Database Ops |
| `pagerduty_service` | String | No | e.g. db-oncall |
| `slack_channel` | String | No | e.g. #db-alerts |
| `tags` | String List | No | e.g. postgres, primary |

---

### NODE 5: EscalationPath

| Field | Value |
|---|---|
| **Node Name** | `EscalationPath` |
| **Description** | `Who gets paged, when, and through which channel per severity level` |

**Properties to add:**

| Property Name | Type | Required | Notes |
|---|---|---|---|
| `path_id` | String | ✅ Yes | Allowed values: P1-path, P2-path, P3-path, P4-path |
| `severity` | String | ✅ Yes | Allowed values: P1, P2, P3, P4 |
| `initial_response_sla` | String | ✅ Yes | e.g. 5 minutes |
| `resolution_target` | String | ✅ Yes | e.g. 2 hours |
| `pagerduty_service` | String | ✅ Yes | e.g. infra-oncall |
| `slack_channel` | String | ✅ Yes | e.g. #incidents-p1 |
| `bridge_call_required` | Boolean | ✅ Yes | true for P1, false for P2/P3/P4 |

---

## SECTION 2 — EDGES / RELATIONSHIPS (Click "Add Relationship +")

For each relationship, click **Add Relationship +** and fill in:
- **Relationship Name** (the label)
- **From Node** → **To Node**
- **Cardinality**

| Relationship Name | From Node | To Node | Cardinality |
|---|---|---|---|
| `TRIGGERED_BY` | Incident | KnowledgeArticle (alert) | Many → One |
| `RESOLVED_BY` | Incident | Resolution | One → One |
| `GUIDED_BY` | Incident | KnowledgeArticle (runbook) | Many → One |
| `AFFECTS` | Incident | System | Many → Many |
| `SIMILAR_TO` | Incident | Incident | Many → Many |
| `ESCALATES_TO` | Incident | EscalationPath | Many → One |
| `TRIAGES` | KnowledgeArticle | KnowledgeArticle (alert) | Many → Many |
| `GOVERNED_BY` | KnowledgeArticle | EscalationPath | Many → One |
| `COVERS_SYSTEM` | KnowledgeArticle | System | Many → Many |
| `RESOLVES` | Resolution | Incident | One → One |

---

## SECTION 3 — ACTIONS (Click "Add Rule +" or Actions tab)

Actions automate behaviours when data changes. Add these:

| Action Name | Trigger | Action |
|---|---|---|
| `PromoteP2ToP1` | Incident: status = open AND severity = P2 AND created_at > 120 min ago | Set severity = P1, create ESCALATES_TO edge to P1-path |
| `RequireResolutionOnClose` | Incident: status changes to resolved | Validate RESOLVED_BY edge exists; block if missing |
| `WarnStaleRunbook` | KnowledgeArticle: article_type = runbook AND updated_at > 180 days | Append staleness warning to retrieval response |
| `BlockStaleRunbook` | KnowledgeArticle: article_type = runbook AND updated_at > 365 days | Block document from RAG retrieval |

---

## SECTION 4 — CONSTRAINTS (Click "Add Rule +" from Constraints tab)

Add each constraint below. For each: provide a **Name**, **Target Node**, **Field**, and **Rule Expression**.

| # | Constraint Name | Target Node | Field | Rule | Severity |
|---|---|---|---|---|---|
| BR-001 | incident_id format | Incident | incident_id | Must match pattern `INC-[0-9]{4,}` | Error |
| BR-002 | severity allowed values | Incident | severity | Must be one of: P1, P2, P3, P4 | Error |
| BR-003 | P1 must have affected_services | Incident | affected_services | If severity = P1 → affected_services must not be empty | Error |
| BR-004 | P2 auto-promotes at 120 min | Incident | severity | If severity = P2 AND open > 120 min → set P1 | Error |
| BR-005 | Resolution required to close | Incident | status | If status = resolved → RESOLVED_BY edge must exist | Error |
| BR-006 | Resolution must have steps | Resolution | resolution_steps | resolution_steps must have at least 1 item | Error |
| BR-007 | Runbook must link to alert | KnowledgeArticle | — | If article_type = runbook → TRIAGES edge must exist | Error |
| BR-008 | Runbook must link to escalation | KnowledgeArticle | — | If article_type = runbook → GOVERNED_BY edge must exist | Error |
| BR-009 | Runbook stale after 180 days | KnowledgeArticle | updated_at | If article_type = runbook AND updated_at > 180 days ago | Warning |
| BR-010 | Content minimum length | KnowledgeArticle | content | content must be at least 200 characters | Error |
| BR-011 | Alert fatigue review | KnowledgeArticle | — | If article_type = alert AND firing > 10/week → warn | Warning |
| BR-012 | Resolution incident_id must exist | Resolution | incident_id | incident_id must reference an existing Incident node | Error |
| BR-013 | P1/P2 must use production systems | Incident | affected_services | If severity in P1/P2 → all AFFECTS targets must have environment = production | Warning |
| BR-014 | EscalationPath steps ordered | EscalationPath | steps | steps[i].at_minutes must be <= steps[i+1].at_minutes | Error |

---

## After Adding Everything

1. Click **Publish Schema** (bottom right button)
2. Go back to the **Context** tab and select this schema
3. Proceed to **Source & Data** to upload your documents
4. Then **Expose via MCP** to connect to IBM Bob
