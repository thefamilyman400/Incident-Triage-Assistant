# High CPU on Database Server Runbook

## Overview
This runbook is designed to help resolve incidents where the CPU usage on a database server exceeds 90% for an extended period. High CPU usage can cause degraded query response times, complete unavailability of services, and impact overall system performance. This runbook will guide you through the steps to identify the root cause, stabilize the system, and implement long-term fixes to prevent recurrence.

## Severity & SLA
| Severity | Response Time | Escalation |
|---|---|---|
| P1 | Immediate | Escalate to Level 2 support if the CPU usage remains high for more than 30 minutes. Escalate to Level 3 support if the incident is not resolved within 1 hour. |

## Prerequisites
- Required tools and access needed before starting triage:
  - SSH access to the database server
  - Database administration privileges
  - Knowledge of database query optimization and indexing

## Immediate Actions (First 5 Minutes)
1. **Check database logs**: Review the database logs to identify any recent queries or processes that may be consuming excessive CPU resources.
2. **Identify resource-intensive processes**: Use `top` or `htop` to identify the processes consuming the most CPU resources.
3. **Check for recent deployments**: Review the change log to ensure there are no recent deployments that may be causing the high CPU usage.

## Diagnostic Commands
```bash
# Check database logs
sudo journalctl -u mysql

# Identify resource-intensive processes
top -c
htop
```

## Root Cause Analysis
The probable root causes of high CPU usage on the database server are:
1. **Resource-intensive query**: A query may be consuming excessive CPU resources due to a missing index or inefficient query plan.
2. **Memory leak**: A memory leak in the database process may be causing the CPU usage to spike.
3. **High-traffic database**: The database may be experiencing high traffic, causing the CPU usage to spike.

## Resolution Steps
1. **Optimize resource-intensive queries**: Review and optimize database queries to ensure they are efficient and do not cause high CPU usage.
2. **Implement query optimization**: Regularly review and optimize database queries to ensure they are efficient and do not cause high CPU usage.
3. **Implement memory monitoring**: Regularly monitor database memory usage to identify potential memory leaks.
4. **Add query timeout**: Add a query timeout to the batch script to prevent runaway processes.
5. **Reschedule high-traffic jobs**: Reschedule high-traffic jobs to a lower-traffic window to prevent CPU spikes.

## Rollback Procedure
If the fix makes things worse, revert the changes by:
1. **Rolling back the deployment**: Roll back the deployment to the previous version.
2. **Removing the query timeout**: Remove the query timeout from the batch script.
3. **Rescheduling the job**: Reschedule the high-traffic job to a lower-traffic window.

## Escalation Criteria
Escalate to Level 2 support if the CPU usage remains high for more than 30 minutes. Escalate to Level 3 support if the incident is not resolved within 1 hour.

## Prevention & IaC Automation
- **Monitor database logs**: Regularly review database logs to identify potential issues before they cause high CPU usage.
- **Implement query optimization**: Regularly review and optimize database queries to ensure they are efficient and do not cause high CPU usage.
- **Implement memory monitoring**: Regularly monitor database memory usage to identify potential memory leaks.
- **IaC templates**: Use IaC templates to automate the deployment of database indexes and query optimization.

## Related Incidents
| Incident ID | Root Cause | Resolution |
|---|---|---|
| INC-2847-HIGH-CPU-BATCH-JOB | Runaway process due to missing query timeout | Terminated the process, added query timeout, and rescheduled the job |
| INC-3012-CPU-MISSING-INDEX | Missing index in the `product_catalog` table | Added the index to the schema migration file for future deployments |

## Sources
- [Source: incidents/INC-2847-HIGH-CPU-BATCH-JOB.md]
- [Source: incidents/INC-3012-CPU-MISSING-INDEX.md]