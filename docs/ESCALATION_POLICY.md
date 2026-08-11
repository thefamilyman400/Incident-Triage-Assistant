# Escalation Policy — Infrastructure & Operations Team
**Version:** 2.4  
**Owner:** Infrastructure Operations  
**Last Updated:** 2025-06-01  
**Review Cycle:** Quarterly

---

## 1. Purpose

This document defines the escalation procedures, severity classifications, response SLAs, and communication protocols for the Infrastructure Operations on-call team. All engineers participating in on-call rotations are required to be familiar with this policy before their first shift.

---

## 2. Severity Definitions & Response SLAs

| Severity | Label | Definition | Initial Response | Resolution Target | Business Impact |
|----------|-------|------------|-----------------|-------------------|-----------------|
| **P1** | Critical | Complete service outage or data loss in production. Customer-facing systems fully unavailable. | **≤ 5 minutes** | ≤ 2 hours | Severe — all customers affected |
| **P2** | High | Significant degradation of a production service. Core functionality impaired; partial customer impact. | **≤ 15 minutes** | ≤ 4 hours | High — subset of customers affected |
| **P3** | Medium | Non-critical service degraded. Workaround available. No immediate customer impact. | **≤ 1 hour** | ≤ 24 hours | Low — internal or minor customer impact |
| **P4** | Low | Informational or cosmetic issue. No service disruption. Can be scheduled for next sprint. | **≤ 1 business day** | Next sprint | Minimal — no customer impact |

> **Severity Escalation Rule:** If a P2 incident has not been resolved within 2 hours, it must be escalated to P1 status automatically.

---

## 3. On-Call Rotation Structure

On-call shifts run in **weekly rotations** (Monday 09:00 → Monday 09:00 local time). All times are US Eastern unless otherwise specified.

### Primary On-Call Schedule

| Week Rotation | Primary On-Call | Secondary On-Call | Escalation Manager |
|---------------|-----------------|-------------------|--------------------|
| Week A | Alex Thompson | Priya Nair | James Okafor |
| Week B | Priya Nair | James Okafor | Divya Sharma |
| Week C | James Okafor | Divya Sharma | Carlos Rivera |
| Week D | Divya Sharma | Carlos Rivera | Alex Thompson |
| Week E | Carlos Rivera | Alex Thompson | Priya Nair |

### Contact Details (Internal Directory)

| Name | Role | PagerDuty Handle | Slack Handle |
|------|------|-----------------|--------------|
| Alex Thompson | Senior SRE | `@alex.thompson` | `@alex.t` |
| Priya Nair | SRE II | `@priya.nair` | `@priya.n` |
| James Okafor | Staff SRE / Escalation Manager | `@james.okafor` | `@james.o` |
| Divya Sharma | SRE II | `@divya.sharma` | `@divya.s` |
| Carlos Rivera | Senior SRE | `@carlos.rivera` | `@carlos.r` |

> Rotation schedule is managed in **PagerDuty** under the `infra-oncall` service. Changes must be submitted via the `#infra-oncall` Slack channel with at least 48 hours notice.

---

## 4. Escalation Matrix

### P1 — Critical

| Time (T+) | Action | Owner |
|-----------|--------|-------|
| T+0 | PagerDuty alert fires; Primary on-call acknowledges | Primary On-Call |
| T+5 min | If unacknowledged, Secondary on-call is paged | PagerDuty (auto) |
| T+10 min | Open bridge call; post in `#incidents-p1` | Primary On-Call |
| T+15 min | Notify Escalation Manager via direct page | Primary On-Call |
| T+30 min | Escalation Manager engages VP Engineering | Escalation Manager |
| T+60 min | Executive stakeholder notification if no resolution ETA | VP Engineering |
| T+120 min | Incident review initiated if still unresolved | Escalation Manager |

### P2 — High

| Time (T+) | Action | Owner |
|-----------|--------|-------|
| T+0 | PagerDuty alert fires; Primary on-call acknowledges | Primary On-Call |
| T+15 min | If unacknowledged, Secondary on-call is paged | PagerDuty (auto) |
| T+30 min | Post status update in `#incidents-p2` | Primary On-Call |
| T+60 min | Notify Escalation Manager if no resolution path identified | Primary On-Call |
| T+120 min | Auto-promote to P1 if unresolved | Escalation Manager |

### P3 — Medium

- Acknowledge within 1 hour during business hours.
- Post update in `#infra-oncall` with investigation status.
- No after-hours page unless severity is re-evaluated.

### P4 — Low

- Ticket created in Jira and triaged during next business day.
- No on-call page required.

---

## 5. Communication Channels

| Channel | Purpose | Who Posts |
|---------|---------|-----------|
| `#infra-oncall` | General on-call coordination, shift handoffs, P3/P4 | All SREs |
| `#incidents-p1` | Live P1 incident war room — all P1 updates | On-call Primary + Manager |
| `#incidents-p2` | Live P2 incident updates | On-call Primary |
| `#infra-alerts` | Raw automated alert feed (do not chat here) | Automated only |
| `#status-updates` | External-facing internal status posts | Escalation Manager+ |

**PagerDuty Services:**
- `infra-oncall` — primary routing for all infrastructure alerts
- `db-oncall` — dedicated database team on-call
- `network-oncall` — network operations on-call

---

## 6. Bridge Call Procedures

Bridge calls are **mandatory for all P1 incidents** and optional but encouraged for P2.

1. **Initiate the bridge:** Dial into the standing Zoom bridge: `https://company.zoom.us/j/infra-incident` (PIN: `8821#`).
2. **Designate roles immediately:**
   - **Incident Commander (IC):** Coordinates response. Usually the Escalation Manager for P1.
   - **Technical Lead:** Primary on-call engineer driving the fix.
   - **Scribe:** Documents actions, findings, and timeline in the incident Slack thread.
   - **Communications Lead:** Posts stakeholder updates (manager or senior SRE).
3. **Bridge cadence:** Status check every 15 minutes; decisions logged in Slack thread.
4. **End bridge:** IC formally closes the bridge once service is confirmed restored.

---

## 7. Stakeholder Notification Templates

### P1 — Initial Notification (T+10 min)

```
🔴 [P1 INCIDENT] <Incident Title>
Time Detected: <HH:MM TZ>
Affected Service(s): <list>
Customer Impact: <description>
Current Status: Investigating
IC: <Name>
Next Update: T+30 min or sooner if status changes
Bridge: https://company.zoom.us/j/infra-incident
```

### P1 — Update Notification (every 30 min)

```
🔴 [P1 UPDATE] <Incident Title> | T+<elapsed>
Current Status: <Investigating / Identified / Mitigating>
Actions Taken: <summary>
ETA to Resolution: <time or "Under investigation">
Next Update: <time>
```

### P1 — Resolution Notification

```
✅ [P1 RESOLVED] <Incident Title>
Resolved At: <HH:MM TZ>
Total Duration: <X hours Y minutes>
Root Cause Summary: <1-2 sentences>
Follow-up: Post-Incident Review scheduled for <date>
```

---

## 8. Post-Incident Handoff Procedures

At the conclusion of any P1 or P2 incident, the outgoing on-call engineer must complete the following before end-of-shift or within 4 hours of resolution:

1. **Incident ticket updated** in Jira with full timeline, root cause, and resolution steps.
2. **Slack thread summarised** — a final pinned message in `#incidents-p1` or `#incidents-p2` with the closure summary.
3. **Action items logged** — all follow-up tasks created as Jira tickets and assigned.
4. **PIR scheduled** — Post-Incident Review must be scheduled within 48 hours for all P1s. Use the `#infra-oncall` channel to coordinate.
5. **Runbook updated** — if existing runbook was insufficient, a PR must be opened within 24 hours.
6. **Metrics recorded** — MTTR, MTTA, and customer impact duration logged in the ops metrics spreadsheet.

> P3 and P4 incidents require only a Jira ticket closure comment. PIRs are optional and at the team lead's discretion.

---

## 9. Escalation Policy Exceptions

- **Scheduled Maintenance:** Alerts triggered during an approved maintenance window are suppressed via PagerDuty maintenance mode. The on-call engineer is still responsible for monitoring the window.
- **Alert Storms:** During a cascading failure, the IC may mute derivative alerts in PagerDuty to reduce noise. This must be documented in the incident thread.
- **Off-Hours P3 Promotion:** If a P3 incident is trending toward customer impact, the on-call engineer has authority to promote to P2 and begin escalation.

---

*For questions about this policy, contact the Infrastructure Operations lead in `#infra-oncall`.*
