# DISK SPACE — Incident Runbook

**Alert Name:** `DISK_SPACE_CRITICAL`
**Severity:** P2 – High (P1 if > 95%)
**Owner:** Platform Operations Team
**Last Updated:** 2024-11-14
**Version:** 2.8

---

## Alert Description

This alert fires when disk utilization on any production filesystem exceeds **85%**. Disk exhaustion is one of the most common causes of complete service outages — many applications and databases will crash or refuse writes when the filesystem reaches 100%.

**Alert Source:** Prometheus → `node_filesystem_avail_bytes`
**Threshold:**
```
(1 - node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes) * 100 > 85
```
**Critical Threshold:** > 95% — auto-escalates to P1 immediately.
**Notification Channel:** PagerDuty → `#ops-alerts` Slack channel

---

## Immediate Actions

> ⚠️ A full disk will cause database corruption, application crashes, and lost logs. Treat this as urgent.

1. **Acknowledge the alert** in PagerDuty.
2. **Identify the affected host and mount point** from the alert labels.
3. **SSH into the affected server:**
   ```bash
   ssh ops-user@<affected-host>
   ```
4. **Check current disk usage across all filesystems:**
   ```bash
   df -h
   # Pay attention to the "Use%" column. Identify which mount point is critical.
   ```
5. **Estimate time to full** — check if usage is actively growing:
   ```bash
   watch -n 30 "df -h /var/log"
   # Run for 2–3 intervals to determine growth rate
   ```
6. **If usage > 95%, immediately free space** — see Quick Wins section below.
7. **Notify on-call engineering** via `#ops-war-room` if the filesystem is > 90% or growing fast.

### Quick Wins (immediate space recovery)

```bash
# Clear systemd journal logs older than 3 days
sudo journalctl --vacuum-time=3d

# Truncate large log files that are actively being written (do NOT delete — truncate)
sudo truncate -s 0 /var/log/app/application.log

# Remove rotated compressed logs
sudo find /var/log -name "*.gz" -mtime +7 -delete
sudo find /var/log -name "*.log.*" -mtime +7 -delete
```

---

## Diagnostic Commands

### Find the Space Hog
```bash
# Top-level breakdown by directory (start broad, drill down)
du -sh /* 2>/dev/null | sort -rh | head -20

# Drill into the largest directory
du -sh /var/* 2>/dev/null | sort -rh | head -20
du -sh /var/log/* 2>/dev/null | sort -rh | head -20

# Find the 20 largest individual files anywhere on the filesystem
find / -xdev -type f -printf '%s %p\n' 2>/dev/null | sort -rn | head -20 | \
  awk '{printf "%.1f MB\t%s\n", $1/1048576, $2}'
```

### Check for Core Dumps
```bash
# Core dumps are often several GB each
find / -xdev -name "core" -o -name "core.[0-9]*" 2>/dev/null
find /var/crash /tmp /home -name "*.core" -o -name "core*" 2>/dev/null

# Check systemd coredump storage
ls -lh /var/lib/systemd/coredump/
coredumpctl list
```

### Check for Deleted Files Still Held Open
```bash
# Files deleted but still consuming space (held open by a running process)
sudo lsof | grep '(deleted)' | awk '{print $7, $1, $2, $9}' | sort -rn | head -20
# Resolution: restart the process holding the file, or truncate its fd:
# sudo truncate -s 0 /proc/<pid>/fd/<fd_number>
```

### Log and Rotation Diagnostics
```bash
# Check log rotation configuration
cat /etc/logrotate.conf
ls /etc/logrotate.d/

# Force immediate log rotation
sudo logrotate -f /etc/logrotate.conf

# Check which services are writing most aggressively
sudo inotifywait -m -r /var/log --format '%w%f %e' 2>/dev/null | head -50
```

### Backup and Archive Files
```bash
# Find old backup archives (tar, zip, sql dumps)
find /var/backups /mnt /opt /home -name "*.tar.gz" -o -name "*.sql.gz" \
  -o -name "*.dump" 2>/dev/null | xargs ls -lh 2>/dev/null | sort -k5 -rh | head -20

# Check backup retention policy
cat /etc/cron.d/backup-cleanup
```

### Database Storage
```bash
# PostgreSQL database sizes
psql -U postgres -c "
  SELECT datname,
         pg_size_pretty(pg_database_size(datname)) AS size
  FROM pg_database
  ORDER BY pg_database_size(datname) DESC;"

# Largest tables in a given database
psql -U postgres -d <dbname> -c "
  SELECT table_name,
         pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS total_size
  FROM information_schema.tables
  WHERE table_schema = 'public'
  ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC
  LIMIT 20;"

# Bloated tables (dead tuples — needs VACUUM)
psql -U postgres -d <dbname> -c "
  SELECT relname, n_dead_tup, n_live_tup,
         round(n_dead_tup::numeric / NULLIF(n_live_tup,0) * 100, 1) AS dead_pct
  FROM pg_stat_user_tables
  ORDER BY n_dead_tup DESC LIMIT 10;"
```

---

## Common Root Causes

| # | Root Cause | Indicators |
|---|-----------|------------|
| 1 | Log accumulation (rotation misconfigured or disabled) | `/var/log` is the space hog; old `.log.*` files present |
| 2 | Core dump files | `core`, `core.*` files in `/tmp`, `/var/crash`, or app dirs |
| 3 | Old backup files not cleaned up | Large `.tar.gz` or `.sql.gz` files in backup dirs |
| 4 | Database table bloat / WAL accumulation | PostgreSQL data dir growing; dead tuple ratio high |
| 5 | Deleted-but-open files | `lsof | grep deleted` shows large entries |
| 6 | Container / Docker image accumulation | `/var/lib/docker` consuming GB+ |
| 7 | Temp files not cleaned up | Large files in `/tmp` or app temp directories |

---

## Resolution Steps

### Cause 1 — Log Accumulation
```bash
# Force log rotation immediately
sudo logrotate -f /etc/logrotate.d/<service>

# If the service's logrotate config is missing, create one:
cat <<'EOF' | sudo tee /etc/logrotate.d/<service>
/var/log/<service>/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    sharedscripts
    postrotate
        systemctl reload <service> > /dev/null 2>&1 || true
    endscript
}
EOF

# Remove already-rotated logs older than 7 days
sudo find /var/log/<service> -name "*.gz" -mtime +7 -delete
```

### Cause 2 — Core Dumps
```bash
# Verify the core dump is no longer needed (confirm with dev team)
coredumpctl list

# Remove old coredumps
sudo coredumpctl clean --until "7 days ago"
sudo rm -f /var/crash/*.core /tmp/core.*
```

### Cause 3 — Old Backups
```bash
# Review before deleting — confirm with the backup owner
find /var/backups -name "*.tar.gz" -mtime +14 -ls

# Delete after confirmation
find /var/backups -name "*.tar.gz" -mtime +14 -delete
```

### Cause 4 — Database Bloat
```bash
# Run VACUUM to reclaim dead tuple space
psql -U postgres -d <dbname> -c "VACUUM VERBOSE ANALYZE <tablename>;"

# Full vacuum (locks table — schedule during low-traffic window)
psql -U postgres -d <dbname> -c "VACUUM FULL <tablename>;"

# Check and archive/purge old partitions if using table partitioning
```

### Cause 5 — Deleted-but-Open Files
```bash
# Identify the process and FD
sudo lsof | grep deleted | sort -k7 -rn | head

# Truncate the file descriptor (frees space without restarting)
sudo truncate -s 0 /proc/<pid>/fd/<fd>

# If safe to do so, restart the process to fully release
sudo systemctl restart <service>
```

### Cause 6 — Docker/Container Accumulation
```bash
# View Docker disk usage summary
docker system df

# Remove stopped containers, unused images, dangling volumes
docker system prune -f

# Remove unused images (aggressive — confirm it's safe)
docker image prune -a -f
```

---

## Escalation Criteria

Escalate to **Engineering Lead (P1)** if any of the following are true:

- Filesystem is > **95%** and no quick-win space can be recovered
- **Database data directory** is affected — risk of corruption
- Disk is **100% full** — services may already be crashing
- Space was freed but **refilled within 1 hour** (indicating active runaway process)
- Root cause cannot be identified within **15 minutes**

**Escalation Path:**
1. On-call SRE → `#ops-war-room`
2. Engineering Lead (PagerDuty: `eng-lead-oncall`)
3. DBA on-call if PostgreSQL data directory is affected

---

## Past Similar Incidents

| Incident ID | Date | Host | Root Cause | Resolution Time |
|-------------|------|------|-----------|-----------------|
| INC-4797 | 2024-10-22 | prod-api-01 | Application writing unbounded debug logs — 40 GB in 6 hours | 30 min |
| INC-4633 | 2024-08-05 | prod-db-01 | PostgreSQL WAL accumulation after failed replication slot cleanup | 1 hr 20 min |
| INC-4401 | 2024-06-18 | prod-worker-02 | Core dump files from OOM-killed worker — 3 × 8 GB dumps | 25 min |
| INC-4100 | 2024-04-02 | prod-api-02 | Backup script silently failing, leaving uncompressed SQL dumps | 45 min |
| INC-3842 | 2024-01-30 | prod-db-02 | Docker image accumulation on build host mounted to prod NFS | 2 hrs |

---

## Related Alerts

- `LOG_VOLUME_ANOMALY` — precursor alert for unexpected log growth
- `DB_REPLICATION_LAG` — replication issues can cause WAL accumulation on primary
- `HIGH_CPU_USAGE` — compaction/vacuum jobs can co-trigger CPU alerts
- `SERVICE_DOWN` — common downstream consequence of a full disk
- `BACKUP_JOB_FAILED` — failed backups may leave partial dump files behind

---

## Notes

- Never use `rm` on an actively-written log file — use `truncate -s 0` instead to avoid breaking the file descriptor.
- Always check with the DBA before deleting anything under `/var/lib/postgresql/` or the DB data directory.
- After recovery, update the logrotate config and verify it runs correctly in the next scheduled window.
- Monitor the filesystem for at least **2 hours** after resolution to confirm growth has stopped.
