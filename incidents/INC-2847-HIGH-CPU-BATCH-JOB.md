# Post-Mortem: INC-2847 — Production DB CPU Spike (Runaway Batch Job)

---

## Incident Metadata

| Field              | Value                                      |
|--------------------|--------------------------------------------|
| **Incident ID**    | INC-2847                                   |
| **Date**           | 2025-06-10                                 |
| **Severity**       | P2 (High)                                  |
| **Status**         | Resolved                                   |
| **Duration**       | 35 minutes (02:14 – 02:49 UTC)             |
| **Affected Server**| prod-db-01                                 |
| **Affected Services** | Order Management API, Reporting Service |
| **On-Call Engineer** | Sarah Mitchell (Platform Engineering)   |
| **Incident Commander** | David Okafor (SRE Lead)              |
| **Postmortem Author** | Sarah Mitchell                          |
| **Review Date**    | 2025-06-12                                 |

---

## Executive Summary

At 02:14 UTC on June 10, 2025, CPU utilization on `prod-db-01` spiked to 98% and remained there for 35 minutes, causing degraded query response times for the Order Management API and complete unavailability of the Reporting Service. The root cause was a nightly data archival batch job that had no query timeout configured, causing it to run an unexpectedly expensive archival query against a 400M-row table without yielding CPU. The incident was resolved by terminating the runaway process, adding a query timeout to the batch script, and rescheduling the job to a lower-traffic window.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| **02:14**  | PagerDuty alert fires: `prod-db-01` CPU > 90% for 5 consecutive minutes. On-call engineer Sarah Mitchell is paged. |
| **02:17**  | Sarah acknowledges alert and begins investigation. Logs into `prod-db-01` via SSH. |
| **02:19**  | `top` and `htop` show `mysqld` consuming 97–98% CPU. No recent deployments flagged in the change log. |
| **02:21**  | Sarah runs `SHOW PROCESSLIST` on MySQL. Identifies a long-running query: `archive_orders_v2.sh` has been executing for 47 minutes against `orders` table (full table scan). |
| **02:23**  | Confirms the query originates from the nightly data archival cron job scheduled at 01:30 UTC. The job is still running — 53 minutes over expected completion time. |
| **02:25**  | David Okafor joins the bridge call. Decision made to kill the runaway process to restore service. |
| **02:26**  | Sarah issues `KILL <process_id>` in MySQL. CPU begins dropping immediately. |
| **02:28**  | CPU returns to baseline (~12%). Order Management API latency normalises. Reporting Service comes back online. |
| **02:31**  | Sarah inspects `archive_orders_v2.sh` — confirms no `--max_statement_time` or `wait_timeout` is set. |
| **02:35**  | Root cause confirmed. Sarah documents findings in the incident ticket. Monitoring channel notified. |
| **02:40**  | Temporary mitigation applied: added `SET SESSION max_statement_time = 300;` to the batch script header. |
| **02:44**  | Batch job re-run in a test environment with the timeout — completes normally in under 4 minutes (data volume smaller in test). Cause identified as missing index on `archived_at` column in production. |
| **02:49**  | Incident declared resolved. Follow-up action items logged. Post-mortem scheduled. |

---

## Root Cause Analysis

### Primary Root Cause
The nightly data archival script (`archive_orders_v2.sh`) executed a bulk `SELECT ... INSERT INTO archive_orders` query against the `orders` table (approximately 400 million rows). The query lacked a `WHERE` clause index on the `archived_at` column, causing a full table scan. Because the script had no query timeout configured, MySQL continued executing the query indefinitely, consuming nearly all available CPU.

### Contributing Factors
- **No query timeout**: The batch script was written without `max_statement_time` or application-level timeout, which is inconsistent with the team's database coding standards.
- **Data volume growth**: The `orders` table has grown 3× in the past 6 months. The archival query was written when the table had ~130M rows and had not been revisited since.
- **Insufficient pre-job validation**: The cron job has no pre-flight check to estimate query cost (via `EXPLAIN`) before executing.
- **Scheduling overlap**: The 01:30 UTC schedule was originally "off-peak" but now partially overlaps with early-morning EU traffic ramp-up.

### Why Wasn't This Caught Earlier?
The batch job has run successfully for 14 months. The performance degradation was gradual as the table grew, and there were no prior alerts because CPU stayed below the 90% threshold until this run.

---

## Impact Assessment

| Dimension         | Detail                                                         |
|-------------------|----------------------------------------------------------------|
| **User Impact**   | ~2,100 active users experienced degraded Order Management UI (slow page loads, timeouts on order history). |
| **Revenue Impact**| Estimated 23 failed order submissions during peak degradation window (02:21–02:28 UTC). |
| **Service Impact**| Reporting Service fully unavailable for 14 minutes. Order Management API p99 latency rose from 180ms to 4,200ms. |
| **Data Impact**   | No data loss. Archival job was terminated mid-run; partial archival state was rolled back by MySQL. |

---

## Resolution Steps

1. Identified the runaway process via `SHOW PROCESSLIST` in MySQL.
2. Terminated the long-running query with `KILL <process_id>`.
3. Verified CPU and service recovery on monitoring dashboards.
4. Added `SET SESSION max_statement_time = 300;` to `archive_orders_v2.sh` as an immediate mitigation.
5. Opened a follow-up ticket to add a proper index on `orders.archived_at` and retest the archival job.
6. Rescheduled the cron job from `01:30 UTC` to `04:00 UTC` to avoid EU traffic overlap.

---

## Lessons Learned

1. **All batch jobs must have query timeouts.** A single runaway query should never be able to saturate a production database server.
2. **Table growth requires periodic query re-evaluation.** Queries that performed well at 100M rows may not scale to 400M rows without index tuning.
3. **Cron schedules should be reviewed quarterly** as traffic patterns evolve.
4. **`EXPLAIN` pre-checks in batch scripts** can catch full table scans before they cause production impact.

---

## Action Items

| # | Action                                                                 | Owner           | Due Date   | Ticket     |
|---|------------------------------------------------------------------------|-----------------|------------|------------|
| 1 | Add `max_statement_time = 300` to all existing batch/archival scripts  | Sarah Mitchell  | 2025-06-17 | PLAT-4401  |
| 2 | Create index on `orders.archived_at` column                            | Raj Patel (DBA) | 2025-06-13 | DB-892     |
| 3 | Reschedule archival cron to 04:00 UTC                                  | Sarah Mitchell  | 2025-06-11 | PLAT-4402  |
| 4 | Add `EXPLAIN` cost pre-check to archival script                        | Tom Nguyen      | 2025-06-20 | PLAT-4403  |
| 5 | Establish coding standard: all DB batch jobs require timeout config    | David Okafor    | 2025-06-24 | PLAT-4404  |
| 6 | Add PagerDuty alert for queries running > 10 minutes                   | Sarah Mitchell  | 2025-06-17 | OBS-210    |

---

## Prevention Measures Implemented

- **Immediate**: Query timeout (`max_statement_time = 300s`) added to `archive_orders_v2.sh`.
- **Immediate**: Cron rescheduled to 04:00 UTC.
- **Short-term**: Index on `orders.archived_at` to be created during next maintenance window (2025-06-13).
- **Process**: New DB Batch Job Checklist added to the team's runbook, requiring timeout, index validation, and estimated runtime sign-off before any batch job is deployed to production.
