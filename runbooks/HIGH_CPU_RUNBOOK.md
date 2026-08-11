# HIGH CPU USAGE — Incident Runbook

**Alert Name:** `HIGH_CPU_USAGE`
**Severity:** P2 – High
**Owner:** Platform Operations Team
**Last Updated:** 2024-11-14
**Version:** 3.1

---

## Alert Description

This alert fires when CPU utilization on any production server exceeds **90%** for a sustained period of **10 or more minutes**. Sustained high CPU can lead to request timeouts, service degradation, and cascading failures across dependent services.

**Alert Source:** Prometheus → `node_cpu_seconds_total`
**Threshold:** `100 - (avg by(instance)(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 90`
**Notification Channel:** PagerDuty → `#ops-alerts` Slack channel

---

## Immediate Actions

> ⚠️ Do not restart the service immediately — gather evidence first.

1. **Acknowledge the alert** in PagerDuty to prevent duplicate pages.
2. **Identify the affected host(s)** from the alert labels (`instance` tag).
3. **SSH into the affected server:**
   ```bash
   ssh ops-user@<affected-host>
   ```
4. **Check current CPU load at a glance:**
   ```bash
   uptime
   # Look for load average values. If 15-min avg > number of vCPUs, system is saturated.
   ```
5. **Open an interactive process view:**
   ```bash
   top -c
   # Press 'P' to sort by CPU, '1' to see per-core breakdown
   ```
6. **Notify the on-call engineering team** via Slack `#ops-war-room` if CPU > 95% or load > 2x vCPU count.
7. **Open a war-room incident thread** if a user-facing impact is confirmed.

---

## Diagnostic Commands

### Identify Top CPU Consumers
```bash
# Snapshot of top 20 CPU-consuming processes
ps aux --sort=-%cpu | head -20

# Real-time per-process CPU (refresh every 2 seconds)
top -b -n 1 -d 2 | head -40

# Check if a single process is spinning
pidstat -u 2 5
```

### Inspect System Load and Scheduling
```bash
# CPU usage breakdown (user, system, iowait, steal)
mpstat -P ALL 5 3

# Context switches and interrupts — high values indicate scheduling pressure
vmstat 2 10

# Check for CPU steal (indicator of noisy neighbour in VM environments)
grep 'steal' /proc/stat
```

### Identify Runaway Application Threads
```bash
# List all threads for a given PID
ps -eLf | grep <pid>

# Thread-level CPU usage
top -H -p <pid>
```

### Database-Specific CPU Diagnostics (PostgreSQL)
```bash
# Check for long-running or CPU-heavy queries
psql -U postgres -c "
  SELECT pid, now() - pg_stat_activity.query_start AS duration,
         query, state, wait_event_type, wait_event
  FROM pg_stat_activity
  WHERE state != 'idle'
    AND query_start < now() - interval '1 minute'
  ORDER BY duration DESC;"

# Check for lock contention
psql -U postgres -c "SELECT * FROM pg_locks WHERE granted = false;"
```

### Check Recent Deployments and Cron Jobs
```bash
# Recent deployments
cat /var/log/deploy.log | tail -50

# Recently triggered cron jobs (may explain CPU spike)
grep CRON /var/log/syslog | tail -30

# Check if any batch job is running
systemctl list-units --type=service --state=running | grep -i batch
```

---

## Common Root Causes

| # | Root Cause | Indicators |
|---|-----------|------------|
| 1 | Runaway application process / infinite loop | Single PID near 100% CPU continuously |
| 2 | Spike in legitimate traffic (autoscale lag) | High CPU spread across multiple processes, rising request rates |
| 3 | Expensive database query or missing index | High CPU on DB host, slow query log entries |
| 4 | Log-heavy debug mode left enabled in production | App process CPU high, log volume unusually large |
| 5 | Background batch job or cron task contention | CPU spike at scheduled time, batch process in `ps` output |
| 6 | Crypto/compression activity (backup, TLS re-keying) | Intermittent; tied to scheduled job |
| 7 | Kernel/OS-level issue (kworker, ksoftirqd) | High CPU on kernel threads, check `dmesg` |

---

## Resolution Steps

### Cause 1 — Runaway Application Process
```bash
# Confirm the offending PID
ps aux --sort=-%cpu | head -5

# Attempt graceful restart of the service first
sudo systemctl restart <service-name>

# If process does not respond to SIGTERM, force kill (last resort)
sudo kill -9 <pid>
```
> 📌 Capture a thread dump before killing: `sudo kill -3 <pid>` (Java) or `gcore <pid>`

### Cause 2 — Traffic Spike
```bash
# Check incoming request rate
tail -f /var/log/nginx/access.log | awk '{print $1}' | sort | uniq -c | sort -rn | head

# Trigger horizontal scaling if autoscaling is configured
kubectl scale deployment <deployment-name> --replicas=<n> -n production

# Temporarily enable rate limiting in NGINX
# Edit /etc/nginx/conf.d/rate_limit.conf, reload: sudo nginx -s reload
```

### Cause 3 — Database Query
```bash
# Kill the offending DB query
psql -U postgres -c "SELECT pg_terminate_backend(<pid>);"

# Check for missing indexes
psql -U postgres -d <dbname> -c "
  SELECT schemaname, tablename, attname, n_distinct, correlation
  FROM pg_stats WHERE tablename = '<table>';"

# Run EXPLAIN ANALYZE on the slow query to identify plan issues
```

### Cause 4 — Debug Logging Enabled
```bash
# Check log level in app config
grep -i 'log_level\|LOG_LEVEL\|debug' /etc/app/config.yaml

# Set to INFO or WARN and reload
sudo sed -i 's/LOG_LEVEL=debug/LOG_LEVEL=info/' /etc/app/environment
sudo systemctl reload <service-name>
```

### Cause 5 — Cron / Batch Job
```bash
# Identify and suspend the offending cron
crontab -l -u <user>
sudo crontab -e  # comment out the job temporarily

# Or suspend a running batch process (SIGSTOP)
kill -STOP <pid>
# Resume later with:
kill -CONT <pid>
```

---

## Escalation Criteria

Escalate to **Engineering Lead (P1)** if any of the following are true:

- CPU remains > 90% for more than **30 minutes** despite mitigation
- The issue affects **more than 2 production hosts** simultaneously
- Application error rates are elevated (> 1% 5xx responses)
- Root cause cannot be identified within **20 minutes**
- The issue reoccurs within **2 hours** of initial resolution

**Escalation Path:**
1. On-call SRE → `#ops-war-room`
2. Engineering Lead (see PagerDuty schedule: `eng-lead-oncall`)
3. VP Engineering if user-facing SLA breach is imminent (> 15 min degradation)

---

## Past Similar Incidents

| Incident ID | Date | Host | Root Cause | Resolution Time |
|-------------|------|------|-----------|-----------------|
| INC-4821 | 2024-09-03 | prod-api-02 | Missing PostgreSQL index on `orders` table causing full table scan | 45 min |
| INC-4655 | 2024-08-17 | prod-worker-01 | Runaway celery worker processing malformed message in queue | 22 min |
| INC-4312 | 2024-06-29 | prod-api-01 | Debug logging accidentally deployed to production | 18 min |
| INC-3988 | 2024-04-11 | prod-db-01 | Autovacuum running against large table during peak hours | 1 hr 10 min |
| INC-3701 | 2024-02-28 | prod-api-03 | Traffic spike from marketing campaign — autoscaling lag | 35 min |

---

## Related Alerts

- `HIGH_MEMORY_USAGE` — often co-occurs with CPU saturation under GC pressure
- `REQUEST_LATENCY_HIGH` — downstream effect of CPU-bound services
- `DB_SLOW_QUERY` — may be driving high CPU on DB hosts
- `POD_RESTART_LOOP` — Kubernetes liveness probe failures caused by CPU starvation

---

## Notes

- Always preserve `/tmp/cpu_dump_<date>.txt` diagnostics before restarting services.
- If `kworker` or `ksoftirqd` are the top consumers, engage the infrastructure team — this is likely a kernel or hardware interrupt issue, not an application problem.
- CPU steal > 5% on a VM indicates hypervisor-level contention — file a ticket with the cloud provider.
