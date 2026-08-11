# Alert Definitions Reference — Infrastructure & Operations
**Version:** 1.9  
**Owner:** Infrastructure Operations / Observability Guild  
**Last Updated:** 2025-06-01  
**Tooling:** Prometheus + Alertmanager, Datadog, PagerDuty  
**Review Cycle:** Quarterly or after any major alert rule change

---

## 1. Purpose

This document provides a canonical reference for all monitored alerts across the production infrastructure stack. It is intended for use by on-call engineers, the Incident Triage Assistant, and observability tooling to correctly classify, route, and respond to alerts.

---

## 2. Alert Definitions Table

| # | Alert Name | Condition / Threshold | Severity | Runbook Link | Owner Team |
|---|------------|-----------------------|----------|--------------|------------|
| 1 | `HighCPUUsage` | CPU utilization > 85% for 5 min on any production host | P2 | [runbook/cpu-high](runbooks/cpu-high.md) | Infra SRE |
| 2 | `CriticalCPUUsage` | CPU utilization > 95% for 2 min on any production host | P1 | [runbook/cpu-critical](runbooks/cpu-critical.md) | Infra SRE |
| 3 | `HighMemoryUsage` | Memory utilization > 80% for 10 min | P2 | [runbook/memory-high](runbooks/memory-high.md) | Infra SRE |
| 4 | `MemoryOOMKill` | OOM kill event detected on any production pod/host | P1 | [runbook/oom-kill](runbooks/oom-kill.md) | Infra SRE |
| 5 | `DiskSpaceWarning` | Disk usage > 75% on any volume | P3 | [runbook/disk-space](runbooks/disk-space.md) | Infra SRE |
| 6 | `DiskSpaceCritical` | Disk usage > 90% on any volume | P1 | [runbook/disk-critical](runbooks/disk-critical.md) | Infra SRE |
| 7 | `NetworkPacketLoss` | Packet loss > 2% over 5 min on any production interface | P2 | [runbook/network-loss](runbooks/network-loss.md) | Network Ops |
| 8 | `NetworkLatencyHigh` | P99 inter-service latency > 500ms over 5 min | P2 | [runbook/network-latency](runbooks/network-latency.md) | Network Ops |
| 9 | `ServiceHealthCheckFail` | Health endpoint returns non-2xx for 3 consecutive checks (30s interval) | P1 | [runbook/service-health](runbooks/service-health.md) | App SRE |
| 10 | `ServiceHealthDegraded` | Health endpoint P95 response time > 2s over 5 min | P2 | [runbook/service-degraded](runbooks/service-degraded.md) | App SRE |
| 11 | `DBConnectionPoolExhausted` | Active DB connections > 90% of pool max for 3 min | P1 | [runbook/db-pool](runbooks/db-pool.md) | Database Ops |
| 12 | `DBConnectionPoolHigh` | Active DB connections > 70% of pool max for 10 min | P2 | [runbook/db-pool](runbooks/db-pool.md) | Database Ops |
| 13 | `DBReplicationLag` | Replica lag > 30 seconds on any read replica | P2 | [runbook/db-replication](runbooks/db-replication.md) | Database Ops |
| 14 | `HighResponseTime` | API P95 response time > 1s over 10 min on any service | P2 | [runbook/response-time](runbooks/response-time.md) | App SRE |
| 15 | `CriticalResponseTime` | API P99 response time > 5s over 5 min on any service | P1 | [runbook/response-time](runbooks/response-time.md) | App SRE |
| 16 | `HighErrorRate` | HTTP 5xx error rate > 1% of total requests over 5 min | P2 | [runbook/error-rate](runbooks/error-rate.md) | App SRE |
| 17 | `CriticalErrorRate` | HTTP 5xx error rate > 5% of total requests over 2 min | P1 | [runbook/error-rate](runbooks/error-rate.md) | App SRE |
| 18 | `SSLCertExpirySoon` | TLS certificate expires in ≤ 30 days | P3 | [runbook/ssl-cert](runbooks/ssl-cert.md) | Infra SRE |
| 19 | `SSLCertExpiryImminent` | TLS certificate expires in ≤ 7 days | P1 | [runbook/ssl-cert](runbooks/ssl-cert.md) | Infra SRE |
| 20 | `BackupJobFailed` | Scheduled backup job exited with non-zero status | P2 | [runbook/backup-failure](runbooks/backup-failure.md) | Database Ops |
| 21 | `BackupJobMissed` | No successful backup completed within 26 hours (daily backup) | P1 | [runbook/backup-failure](runbooks/backup-failure.md) | Database Ops |
| 22 | `K8sPodRestartHigh` | Pod restart count > 5 within 15 min in any namespace | P2 | [runbook/pod-restarts](runbooks/pod-restarts.md) | Platform SRE |
| 23 | `K8sPodCrashLooping` | Pod in `CrashLoopBackOff` state for > 5 min | P1 | [runbook/pod-crashloop](runbooks/pod-crashloop.md) | Platform SRE |
| 24 | `K8sNodeNotReady` | Kubernetes node in `NotReady` state for > 2 min | P1 | [runbook/node-notready](runbooks/node-notready.md) | Platform SRE |
| 25 | `JVMHeapUsageHigh` | JVM heap utilization > 80% (post-GC) over 10 min | P2 | [runbook/jvm-heap](runbooks/jvm-heap.md) | App SRE |
| 26 | `JVMHeapUsageCritical` | JVM heap utilization > 95% (post-GC) over 3 min | P1 | [runbook/jvm-heap](runbooks/jvm-heap.md) | App SRE |
| 27 | `MessageQueueDepthHigh` | Queue depth > 10,000 messages and consumer lag growing over 10 min | P2 | [runbook/queue-depth](runbooks/queue-depth.md) | App SRE |
| 28 | `MessageQueueDepthCritical` | Queue depth > 100,000 messages or consumer group stopped | P1 | [runbook/queue-depth](runbooks/queue-depth.md) | App SRE |
| 29 | `LogErrorRateHigh` | Application log error rate > 50 errors/min over 5 min | P2 | [runbook/log-errors](runbooks/log-errors.md) | App SRE |
| 30 | `LogErrorRateCritical` | Application log error rate > 500 errors/min over 2 min | P1 | [runbook/log-errors](runbooks/log-errors.md) | App SRE |

---

## 3. Alert Fatigue Notes — Known Noisy Alerts

The following alerts have a history of elevated false-positive rates. Engineers should apply additional scrutiny before escalating incidents triggered solely by these alerts.

| Alert Name | Noise Reason | Recommended Action |
|------------|--------------|--------------------|
| `HighCPUUsage` | Fires during routine batch jobs (nightly ETL, 02:00–04:00 UTC). Normal behaviour. | Verify against scheduled job calendar before escalating. Suppression rule in maintenance window recommended. |
| `DiskSpaceWarning` | Log rotation occasionally lags, causing transient spikes. Self-clears within 30 min. | Confirm disk usage is still elevated 30 min after alert fires. |
| `K8sPodRestartHigh` | Rolling deployments trigger restart counts. Fires on every standard deploy. | Cross-check with deployment pipeline; suppress if a deploy is in progress. |
| `DBConnectionPoolHigh` | Spikes during reporting jobs (weekday 07:00–08:00 UTC). Known and accepted. | Verify against reporting job schedule. If outside this window, investigate. |
| `NetworkLatencyHigh` | Occasionally triggered by cross-region health checks during cloud provider maintenance. | Check cloud provider status page first before engaging network team. |
| `LogErrorRateHigh` | Some upstream integration partners return transient 5xx errors during their own maintenance windows. | Check partner status page and existing suppression schedules. |

> **Alert Fatigue Policy:** Any alert firing > 10 times per week without actionable outcome must be reviewed by the Observability Guild within 2 weeks. Open a ticket tagged `observability-review` in Jira.

---

## 4. Silencing & Suppression Guidelines

### 4.1 When to Silence an Alert

Alerts may be silenced in Alertmanager or PagerDuty under the following conditions only:

- A **maintenance window** is in effect and the alert is expected behaviour.
- The alert is a **known duplicate** of a higher-severity alert already being actively worked.
- An **alert storm** is in progress and derivative alerts are adding no diagnostic value (IC must approve).

### 4.2 How to Create a Silence

**Alertmanager (Prometheus):**
```bash
# Via UI: https://alertmanager.internal/silences → "New Silence"
# Via CLI:
amtool silence add \
  alertname="<AlertName>" \
  --duration="2h" \
  --comment="Maintenance window: <JIRA-XXXX> — <Your Name>"
```

**PagerDuty:**  
Navigate to `Services → infra-oncall → Maintenance Windows → Add Window`.

> **Rule:** All silences must include a Jira ticket reference and an owner. Silences without a comment will be removed automatically by the compliance sweep job (`silence-audit` cron, runs hourly).

### 4.3 Maximum Silence Duration

| Scenario | Max Silence Duration |
|----------|----------------------|
| Scheduled maintenance | Duration of maintenance window + 30 min buffer |
| Alert storm suppression | 2 hours (must be renewed with IC approval) |
| Known noisy alert (pending fix) | 7 days (requires manager approval) |

---

## 5. Maintenance Window Procedures

1. **Schedule in advance:** Maintenance windows must be registered in PagerDuty and announced in `#infra-oncall` at least **4 hours** before start (24 hours for customer-impacting maintenance).
2. **Create the window in PagerDuty:** Set affected services, start/end time, and a clear description referencing the change ticket.
3. **Suppress in Alertmanager:** Apply label-matched silences for all expected alerts for the duration.
4. **Assign a monitor:** On-call primary is responsible for watching for unexpected alerts during the window.
5. **Close the window on time:** Remove PagerDuty maintenance mode immediately upon completion. Do not leave windows open past their scheduled end.
6. **Post-maintenance check:** Verify all expected services return to green within 15 minutes of maintenance completion.

---

## 6. Alert Routing Rules

Alerts are routed based on `team` label set in the Prometheus alert rule. Routing is configured in Alertmanager `routes` config.

| Team Label | PagerDuty Service | Slack Channel | Escalation Path |
|------------|-------------------|---------------|-----------------|
| `infra-sre` | `infra-oncall` | `#infra-alerts` | Infra SRE on-call → ESCALATION_POLICY.md |
| `app-sre` | `infra-oncall` | `#infra-alerts` | App SRE on-call → ESCALATION_POLICY.md |
| `database-ops` | `db-oncall` | `#db-alerts` | DB on-call → DBA escalation chain |
| `network-ops` | `network-oncall` | `#network-alerts` | Network Ops on-call → NetEng manager |
| `platform-sre` | `infra-oncall` | `#platform-alerts` | Platform SRE on-call → ESCALATION_POLICY.md |

### P1 Override Routing

Regardless of team label, **all P1 alerts** are simultaneously routed to:
- PagerDuty `infra-oncall` (high-urgency policy, phone call)
- Slack `#incidents-p1` (automated bot post)
- Email DL: `infra-ops-oncall@company.com`

---

## 7. Adding or Modifying Alert Rules

All changes to alert thresholds or new alert definitions must follow this process:

1. Open a PR against the `infra-config` repository, path `alerting/rules/`.
2. Tag reviewers: at least one member of the Observability Guild and the owning team lead.
3. Include in the PR description: alert name, rationale for threshold, runbook link (must exist before merge), expected false positive rate.
4. After merge, update this document in the same PR or a follow-up PR within 24 hours.
5. Announce the change in `#infra-oncall` after deployment.

---

*For questions about specific alert behaviour, contact the Observability Guild in `#observability` or open a Jira ticket with label `alert-definition`.*
