# SERVICE DOWN — Incident Runbook

**Alert Name:** `SERVICE_HEALTH_CHECK_FAILING`
**Severity:** P1 – Critical
**Owner:** Platform Operations Team
**Last Updated:** 2024-11-14
**Version:** 4.2

---

## Alert Description

This alert fires when a service's HTTP health check endpoint returns a non-2xx response, times out, or becomes unreachable for **2 or more consecutive checks** (check interval: 30 seconds). This indicates the service is fully or partially unavailable and customer-facing impact is likely.

**Alert Source:** Blackbox Exporter / Kubernetes liveness probe
**Health Check Endpoint:** `GET /health` or `GET /actuator/health`
**Threshold:** 2 consecutive failures (60-second confirmation window)
**Notification Channel:** PagerDuty (P1 auto-page) → `#ops-incidents`

---

## Immediate Actions

> 🚨 This is a P1 incident. Customer impact is assumed until proven otherwise.

1. **Acknowledge the alert** in PagerDuty immediately to prevent escalation page.
2. **Verify the outage is real** (rule out monitoring flap):
   ```bash
   curl -sv https://<service-host>/health
   # Look for HTTP 200 and a healthy JSON body, e.g. {"status":"UP"}
   ```
3. **Check the status page** and confirm if an incident is already declared:
   - Internal: `http://statuspage.internal`
4. **Open an incident** in the incident management tool (Statuspage / OpsGenie):
   - Title: `[P1] <Service Name> — Health check failing`
   - Notify: `#ops-war-room`, `#eng-oncall`
5. **Do not immediately rollback** — gather logs and understand the failure mode first.
6. **Set a 10-minute assessment checkpoint** — if root cause is not identified, begin rollback procedure.

---

## Diagnostic Commands

### Check Service Status (Systemd)
```bash
# Is the service unit running?
sudo systemctl status <service-name>

# View recent logs from the service
sudo journalctl -u <service-name> -n 100 --no-pager

# Follow logs in real time
sudo journalctl -u <service-name> -f

# Check for crash loops (check exit code)
sudo journalctl -u <service-name> --since "1 hour ago" | grep -i "exit\|fail\|error\|killed"
```

### Check Service Status (Kubernetes)
```bash
# Get pod status — look for CrashLoopBackOff, OOMKilled, Error
kubectl get pods -n production -l app=<service-name>

# Describe pod for detailed events (look at Events section at bottom)
kubectl describe pod <pod-name> -n production

# View live pod logs
kubectl logs <pod-name> -n production --tail=100 -f

# View logs from the previously crashed container
kubectl logs <pod-name> -n production --previous

# Check recent pod restart count
kubectl get pods -n production -l app=<service-name> \
  -o custom-columns="NAME:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount,STATUS:.status.phase"
```

### Check Service Status (Docker)
```bash
# List containers and their status
docker ps -a | grep <service-name>

# View last 100 log lines
docker logs --tail 100 <container-name>

# Inspect container exit code and restart policy
docker inspect <container-name> | jq '.[].State'

# Restart the container (only after gathering logs)
docker restart <container-name>
```

### Check Application Error Logs
```bash
# Application log (adjust path as appropriate)
tail -200 /var/log/app/<service>.log | grep -E "ERROR|FATAL|Exception|panic"

# Check for OOM kills in kernel log
sudo dmesg | grep -i "killed process\|oom" | tail -20

# Auth/permission failures that might block startup
sudo grep -i "permission denied\|EACCES" /var/log/app/<service>.log | tail -20
```

### Dependency Health Checks
```bash
# Check database connectivity
pg_isready -h <db-host> -p 5432 -U <dbuser>
psql -U <dbuser> -h <db-host> -c "SELECT 1;" 2>&1

# Check Redis connectivity
redis-cli -h <redis-host> -p 6379 ping

# Check downstream HTTP dependencies
curl -sv --max-time 5 http://<dependency-service>/health

# Check if required ports are listening
ss -tlnp | grep -E '8080|5432|6379|9200'
```

### Check Kubernetes Service and Ingress
```bash
# Verify service endpoints are populated (empty = no healthy pods)
kubectl get endpoints <service-name> -n production

# Check ingress configuration
kubectl describe ingress <ingress-name> -n production

# Check HPA (horizontal pod autoscaler) status
kubectl get hpa -n production

# View recent deployment events
kubectl rollout history deployment/<service-name> -n production
```

---

## Common Root Causes

| # | Root Cause | Indicators |
|---|-----------|------------|
| 1 | Bad deployment / code defect | Crash immediately after recent deployment; check deploy log |
| 2 | OOM kill (out of memory) | `OOMKilled` in pod status; `dmesg` shows kill events |
| 3 | Database connection pool exhausted | DB error in logs: "too many connections" / "connection refused" |
| 4 | Dependency service unavailable | Health check logs show failed downstream calls |
| 5 | Configuration/secret misconfiguration | Service exits on startup; "config not found" in logs |
| 6 | Liveness probe misconfigured (too aggressive) | Pod restarting but process is healthy; check probe settings |
| 7 | Certificate expiry | TLS handshake errors; `openssl` reports expired cert |

---

## Resolution Steps

### Cause 1 — Bad Deployment (Rollback Procedure)
```bash
# Check what version is currently deployed
kubectl rollout history deployment/<service-name> -n production

# Roll back to the previous known-good revision
kubectl rollout undo deployment/<service-name> -n production

# Or roll back to a specific revision
kubectl rollout undo deployment/<service-name> --to-revision=<N> -n production

# Watch rollout progress
kubectl rollout status deployment/<service-name> -n production --timeout=5m

# Verify health after rollback
curl -s https://<service-host>/health | jq .
```

### Cause 2 — OOM Kill
```bash
# Confirm OOM kill
kubectl describe pod <pod-name> -n production | grep -A5 "OOMKilled"

# Temporarily increase memory limit (edit deployment)
kubectl set resources deployment/<service-name> -n production \
  --limits=memory=2Gi --requests=memory=1Gi

# Then investigate heap dumps / memory leak with dev team
```

### Cause 3 — DB Connection Pool Exhausted
```bash
# Check current DB connection count
psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"
psql -U postgres -c "SHOW max_connections;"

# Kill idle connections (use with caution)
psql -U postgres -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE state = 'idle'
    AND state_change < now() - interval '5 minutes'
    AND datname = '<dbname>';"

# Restart PgBouncer if in use
sudo systemctl restart pgbouncer
```

### Cause 4 — Downstream Dependency Failure
```bash
# Confirm which dependency is failing from service logs
grep -i "connection refused\|timeout\|ECONNREFUSED" /var/log/app/<service>.log | tail -20

# Check if the dependency has its own active incident
# Navigate to: http://statuspage.internal

# If dependency is non-critical, verify circuit breaker is open and service degrades gracefully
```

### Cause 5 — Configuration / Secret Issue
```bash
# Check if secrets are mounted correctly in Kubernetes
kubectl describe pod <pod-name> -n production | grep -A10 "Volumes\|Environment"

# Verify secret exists
kubectl get secret <secret-name> -n production

# Recreate secret from vault if missing
vault kv get -field=value secret/prod/<service-name> | \
  kubectl create secret generic <secret-name> --from-literal=key=- -n production
```

---

## Escalation Criteria

Escalate to **Engineering Lead / VP Engineering (P0)** if:

- Service has been down for more than **15 minutes** with no ETA on fix
- Rollback fails or makes the situation worse
- The incident affects **multiple services simultaneously** (possible infrastructure failure)
- Data integrity issues are suspected (corruption, partial writes)
- SLA breach window is reached (defined in SLA: 99.9% uptime = max 43 min/month)

**Escalation Path:**
1. On-call SRE → `#ops-war-room` (immediate)
2. Engineering Lead (PagerDuty: `eng-lead-oncall`) at T+10 min if unresolved
3. VP Engineering at T+20 min if unresolved
4. Customer Success to notify enterprise customers at T+15 min

---

## Post-Incident Actions

After service is restored:
- [ ] Update incident status page to "Resolved"
- [ ] Write preliminary post-mortem within 24 hours
- [ ] Confirm monitoring shows clean health checks for 15+ minutes
- [ ] Review and fix liveness/readiness probe settings if they contributed
- [ ] Schedule full post-mortem within 5 business days

---

## Past Similar Incidents

| Incident ID | Date | Service | Root Cause | Downtime |
|-------------|------|---------|-----------|----------|
| INC-4891 | 2024-11-01 | payment-service | New deployment missing DB migration — startup crash loop | 18 min |
| INC-4744 | 2024-09-20 | user-api | OOMKilled after memory leak introduced in v2.14.1 | 32 min |
| INC-4502 | 2024-07-14 | auth-service | Expired TLS certificate on mutual-TLS connection to identity provider | 27 min |
| INC-4289 | 2024-05-08 | notification-svc | Redis cluster failover caused connection pool exhaustion | 11 min |
| INC-3995 | 2024-03-22 | order-processor | Kubernetes liveness probe timeout too short — killed healthy pods | 45 min |

---

## Related Alerts

- `HIGH_CPU_USAGE` — CPU starvation can cause health checks to time out
- `DISK_SPACE_CRITICAL` — full disk causes application startup failure
- `DB_CONNECTION_POOL_EXHAUSTED` — common cause of service unresponsiveness
- `DEPLOYMENT_FAILED` — bad rollout is the most common trigger for this alert
- `CERTIFICATE_EXPIRY` — TLS cert expiry causes health check failures silently

---

## Notes

- Always grab logs **before** restarting a crashed container — logs are lost on restart in many configurations.
- In Kubernetes, use `kubectl logs --previous` immediately after a crash to capture the terminal output.
- For Java services, attempt to capture a heap dump before killing: `jcmd <pid> VM.heap_dump /tmp/heapdump.hprof`
- Coordinate with the Customer Success team early for P1 incidents — proactive communication reduces customer escalations.
