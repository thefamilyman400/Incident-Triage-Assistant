# PERMISSION & OWNERSHIP DRIFT — Incident Runbook

**Alert Name:** `PERMISSION_DRIFT_DETECTED` / `SERVICE_STARTUP_FAILURE`
**Severity:** P1 – Critical (daemons failing to start) / P2 – High (degraded permissions detected)
**Owner:** Platform Operations Team
**Last Updated:** 2025-06-01
**Version:** 1.0

---

## Alert Description

This alert fires when one or more system daemons fail to start or crash immediately after startup due to incorrect file permissions or ownership on critical system directories (`/var`, `/etc`, `/usr`, `/run`, `/tmp`, or application-specific paths). The most common trigger is an accidental **recursive `chmod` or `chown`** command executed against a system directory, which silently overwrites permissions on hundreds or thousands of files at once.

**Alert Source:** Systemd unit failure events → `journalctl`, Prometheus `node_systemd_unit_state`
**Threshold:** Any production daemon exits with `EACCES` (permission denied) or `EPERM` on startup
**Notification Channel:** PagerDuty → `#ops-alerts` → `#ops-war-room`

> 🚨 This class of incident has a very wide blast radius. A single bad `chmod -R` on `/etc` can break SSH, sudo, cron, and every service on the host simultaneously.

---

## Immediate Actions

> ⚠️ **Do not run any further `chmod` or `chown` commands** until you fully understand the scope. Additional changes will make recovery harder.

1. **Acknowledge the alert** in PagerDuty immediately.
2. **Do not reboot the host** — the system may not come back up if `/etc/init.d`, PAM, or SSH host keys have wrong permissions.
3. **Determine which services are affected:**
   ```bash
   # List all failed systemd units
   systemctl --failed --no-legend

   # Check the specific failure reason for each
   systemctl status <service-name> --no-pager -l
   ```
4. **Confirm permission drift is the root cause** — look for `EACCES` or `Permission denied` in the service logs:
   ```bash
   sudo journalctl -u <service-name> -n 50 --no-pager | grep -iE "permission denied|EACCES|EPERM|cannot open"
   ```
5. **Identify the scope of the drift** — check if core system directories are affected:
   ```bash
   # Quick triage — compare permissions on known critical files
   ls -la /etc/passwd /etc/shadow /etc/sudoers /etc/ssh/sshd_config
   # Expected:
   #   /etc/passwd   → -rw-r--r-- root root
   #   /etc/shadow   → -rw-r----- root shadow  (or 000 on some distros)
   #   /etc/sudoers  → -r--r----- root root  (440)
   #   /etc/ssh/sshd_config → -rw-r--r-- root root  (644)
   ```
6. **Open a war-room incident** in `#ops-war-room` immediately if more than one service is affected.
7. **Preserve shell access** — keep your current SSH session alive. If your session drops and permissions are broken, recovery requires console/OOB access.

---

## Diagnostic Commands

### Identify What Changed and When

```bash
# Find files whose permissions were modified in the last 2 hours
sudo find /etc /var /usr/bin /usr/sbin -newer /tmp/.perm-check-ref \
  -not -type l 2>/dev/null | head -50
# (Create reference file first: touch -t $(date -d '2 hours ago' +%Y%m%d%H%M) /tmp/.perm-check-ref)

# Check bash/shell history for recent chmod/chown commands
cat ~/.bash_history | grep -E "chmod|chown" | tail -30
cat /root/.bash_history | grep -E "chmod|chown" | tail -30

# Check audit log for chmod/chown syscalls (if auditd is running)
sudo ausearch -sc chmod --start recent 2>/dev/null | tail -50
sudo ausearch -sc chown --start recent 2>/dev/null | tail -50

# Check sudo log for recent privileged commands
sudo grep -E "chmod|chown" /var/log/auth.log | tail -30
sudo grep -E "chmod|chown" /var/log/secure | tail -30      # RHEL/CentOS
```

### Assess the Full Scope

```bash
# Check setuid/setgid binaries — these MUST have correct permissions
# Compare against a known-good list if available
find /usr/bin /usr/sbin /bin /sbin -perm /6000 -type f -ls 2>/dev/null

# Check critical setuid binaries specifically
ls -la /usr/bin/sudo /usr/bin/passwd /usr/bin/su /usr/bin/newgrp

# Expected for sudo:
#   -rwsr-xr-x root root /usr/bin/sudo   (4755 or 4111)

# Check SSH key permissions
ls -la /etc/ssh/
# Expected: host private keys → 600 root root
#           host public keys  → 644 root root

# Check cron directories
ls -la /etc/cron.d/ /etc/cron.daily/ /var/spool/cron/

# Check PAM configuration ownership
ls -la /etc/pam.d/ | head -20
```

### Check Service-Specific Paths

```bash
# For each failed service, find its working directories and config files
systemctl cat <service-name> | grep -E "User=|Group=|WorkingDirectory=|ExecStart="

# Check ownership of those paths
ls -la /var/lib/<service-name>/
ls -la /var/run/<service-name>/
ls -la /etc/<service-name>/

# Check if the service user still exists and has correct UID
id <service-user>
grep <service-user> /etc/passwd
```

### Check for Broken sudo / SSH Access

```bash
# Verify sudo still works (run from a non-root session)
sudo -l 2>&1 | head -10
# If this returns "sudo: /etc/sudoers is world writable" or similar → CRITICAL

# Verify SSH daemon config is readable
sudo sshd -t 2>&1
# Expected: no output (exit 0). Any error means SSH config is broken.

# Check sshd is still running
systemctl status sshd --no-pager
```

---

## Common Root Causes

| # | Root Cause | Indicators |
|---|-----------|------------|
| 1 | Recursive `chmod` on `/var` or `/etc` | All files in directory have identical permissions; history shows `chmod -R` |
| 2 | Recursive `chown` changed owner away from root/service user | Service logs show `EACCES`; `ls -la` shows wrong owner on config/data dirs |
| 3 | Deployment script ran `chmod -R 777` on application dir that included system mounts | Multiple unrelated services broken after a deploy |
| 4 | `rsync` or `cp --no-preserve` overwrote permissions from a dev/staging source | Permissions match a non-production environment; triggered after a sync job |
| 5 | Incorrect Ansible/Puppet/Chef task applied wrong `mode:` or `owner:` recursively | Permissions changed shortly after a config management run |
| 6 | Container volume mount leaked incorrect permissions into host path | Docker/Kubernetes volume with `runAsUser` mismatch |

---

## Resolution Steps

### Cause 1 & 2 — Restore Known-Good Permissions (Targeted Recovery)

If only specific directories are affected and the correct permissions are known:

```bash
# --- Common system directory permission baselines ---

# /etc — config files should generally be root:root 644, dirs 755
sudo find /etc -type f -not -name "shadow" -not -name "sudoers" \
  -exec chmod 644 {} \;
sudo find /etc -type d -exec chmod 755 {} \;
sudo chown -R root:root /etc

# Restore critical files that must NOT be world-readable
sudo chmod 640 /etc/shadow
sudo chown root:shadow /etc/shadow
sudo chmod 440 /etc/sudoers
sudo chown root:root /etc/sudoers
sudo chmod 600 /etc/ssh/ssh_host_*_key        # private keys
sudo chmod 644 /etc/ssh/ssh_host_*_key.pub    # public keys

# /var/lib/<service> — typically owned by the service user
sudo chown -R <service-user>:<service-group> /var/lib/<service-name>/
sudo chmod 750 /var/lib/<service-name>/

# /var/run (runtime sockets/PIDs)
sudo chown -R <service-user>:<service-group> /var/run/<service-name>/
sudo chmod 755 /var/run/<service-name>/

# Restore setuid bit on critical binaries (ONLY after confirming correct binary)
sudo chmod 4755 /usr/bin/sudo
sudo chmod 4755 /usr/bin/passwd
sudo chmod 4755 /usr/bin/su
```

> 📌 After restoring each path, restart the affected service immediately and confirm it starts cleanly before moving to the next.

### Cause 1 & 2 — Full System Permission Restore (Nuclear Option)

If the recursive change was broad (e.g., `chmod -R 777 /etc`) and targeted recovery is not feasible, use the package manager to restore RPM/DEB-owned file permissions:

```bash
# Debian / Ubuntu — restore permissions for all installed packages
sudo dpkg --verify 2>/dev/null | awk '{print $2}' | while read pkg; do
  sudo dpkg --status "$pkg" &>/dev/null && \
  sudo dpkg-reconfigure "$pkg" 2>/dev/null
done

# Or more aggressively — reinstall all packages to restore permissions
sudo dpkg --get-selections | awk '{print $1}' | \
  sudo xargs apt-get install --reinstall -y 2>/dev/null

# RHEL / CentOS / Rocky — restore permissions for all RPM-owned files
sudo rpm -qa | xargs sudo rpm --setperms 2>/dev/null
sudo rpm -qa | xargs sudo rpm --setugids 2>/dev/null

# Verify a specific package's file permissions were restored
rpm -V <package-name>       # RHEL — lists files with wrong permissions
dpkg --verify <package>     # Debian — same
```

> ⚠️ These commands can take 5–30 minutes on a large system. Do not interrupt them.

### Cause 3 — Deployment Script Applied Wrong Permissions

```bash
# Roll back the deployment that triggered the permission change
kubectl rollout undo deployment/<service-name> -n production

# Or re-run the deploy pipeline with the corrected chmod/chown target path
# Fix the script to scope the permission change to the app directory only:
# BAD:  chmod -R 755 /var/app/
# GOOD: chmod -R 755 /var/app/myservice/   ← explicit, non-system path
```

### Cause 5 — Config Management Tool (Ansible / Puppet)

```bash
# Identify the task that caused the drift
# Ansible — check the last run log
cat /var/log/ansible.log | grep -E "chmod|chown|file|mode" | tail -50

# Roll back the playbook change and re-run with corrected mode/owner values
# Then run the corrected playbook to restore permissions:
ansible-playbook site.yml --tags permissions --limit <affected-host>
```

---

## Restart and Verify Services

After restoring permissions, restart each failed service and verify:

```bash
# Restart service
sudo systemctl daemon-reload
sudo systemctl restart <service-name>

# Confirm it started cleanly
sudo systemctl status <service-name> --no-pager -l

# Confirm no permission errors in logs
sudo journalctl -u <service-name> -n 30 --no-pager | \
  grep -iE "permission denied|EACCES|EPERM|started|failed"

# Run a full health check
curl -sv https://<service-host>/health
```

---

## Escalation Criteria

Escalate to **Engineering Lead / Infrastructure Lead (P0)** immediately if:

- **SSH or sudo is broken** — you may lose remote access to the host entirely
- The affected directories include `/bin`, `/sbin`, `/usr/bin`, or `/usr/sbin` — the system may be unbootable after a reboot
- More than **3 production hosts** are affected simultaneously
- Root cause cannot be identified within **15 minutes**
- Package manager restore fails or produces errors

**Escalation Path:**
1. On-call SRE → `#ops-war-room` (immediate)
2. Infrastructure Lead (PagerDuty: `infra-lead-oncall`) at T+10 min
3. Request **OOB / console access** from data centre / cloud provider if SSH is broken
4. VP Engineering at T+20 min if multiple hosts are affected or recovery is uncertain

---

## Past Similar Incidents

| Incident ID | Date | Host | Root Cause | Resolution Time |
|-------------|------|------|-----------|-----------------|
| INC-3788 | 2024-01-18 | prod-app-01 | Ansible task used `mode: 0777` with `recurse: yes` on `/var/lib/myapp` — `/var/lib` affected | 55 min |
| INC-3544 | 2023-11-04 | prod-db-02 | Engineer ran `sudo chown -R appuser:appuser /var` instead of `/var/lib/myapp` — PostgreSQL ownership broken | 1 hr 40 min |
| INC-3201 | 2023-08-22 | prod-worker-03 | Deploy script ran `chmod -R 755 /etc/myapp/` — `/etc/ssh` permissions cleared, SSH daemon rejected connections | 2 hrs (required OOB console) |
| INC-2944 | 2023-06-10 | prod-api-01 | `rsync` job synced from staging with `--chmod=644` flag set globally — wiped setuid bit on `/usr/bin/sudo` | 30 min |

---

## Related Alerts

- `ServiceHealthCheckFail` — most affected daemons will immediately trigger health check failures
- `K8sPodCrashLooping` — containerised services will enter CrashLoopBackOff if volume-mounted config files lose correct permissions
- `LogErrorRateCritical` — cascading permission failures across services will spike error rates
- `BackupJobFailed` — backup agents are commonly broken by `/var` permission drift
- `SSLCertExpiryImminent` — cert renewal daemons (certbot, acme.sh) failing silently due to permission errors

---

## Notes

- **Keep your SSH session alive at all costs.** If the session drops after permissions are broken, recovery requires console or OOB (IPMI/iDRAC/ILO) access, which may require a separate ticket and delay resolution significantly.
- Always **scope `chmod` and `chown` to the most specific path possible.** Never run recursive permission commands on `/`, `/var`, `/etc`, `/usr`, or `/run` without an explicit, reviewed plan.
- After recovery, run `sudo -l` and `sudo sshd -t` as a final sanity check before declaring the incident resolved.
- Consider enabling `auditd` rules to alert on any future `chmod`/`chown` calls against system directories — this provides both detection and forensic evidence.
- Add a mandatory peer-review gate in your CI/CD pipeline for any playbook or script containing `chmod -R` or `chown -R`.
