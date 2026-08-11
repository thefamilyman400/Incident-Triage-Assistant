# Post-Mortem: INC-3455 — Disk Space Full / Service Degradation (Log Rotation Misconfiguration)

---

## Incident Metadata

| Field               | Value                                                  |
|---------------------|--------------------------------------------------------|
| **Incident ID**     | INC-3455                                               |
| **Date**            | 2025-07-14                                             |
| **Severity**        | P3 (Medium)                                            |
| **Status**          | Resolved                                               |
| **Duration**        | 20 minutes (11:22 – 11:42 UTC)                         |
| **Affected Server** | prod-app-03                                            |
| **Affected Services** | Inventory Service, Admin Dashboard              |
| **On-Call Engineer** | Carlos Rivera (Infrastructure Engineering)           |
| **Incident Commander** | Sarah Mitchell (Platform Engineering)             |
| **Postmortem Author** | Carlos Rivera                                       |
| **Review Date**     | 2025-07-16                                             |

---

## Executive Summary

At 11:22 UTC on July 14, 2025, a disk space alert fired for `prod-app-03`, reporting the `/var/log` partition at 98% capacity. Shortly after, the Inventory Service and Admin Dashboard on that host began logging write errors and returning degraded responses as application log buffers overflowed. The root cause was a misconfigured `logrotate` configuration following an OS upgrade performed the previous week — the upgrade replaced the application-specific logrotate drop-in configuration with the OS default, disabling rotation for the application logs and allowing them to accumulate unchecked for 7 days. The incident was resolved in 20 minutes by manually rotating logs, clearing space, and restoring the correct logrotate configuration.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| **11:22**  | PagerDuty alert fires: `prod-app-03` disk partition `/var/log` at 98% capacity. Carlos Rivera paged. |
| **11:24**  | Carlos acknowledges. Checks Datadog host dashboard for `prod-app-03`. Confirms `/var/log` at 98% (47.1 GB used of 48 GB). |
| **11:25**  | Carlos SSHes to `prod-app-03`. Runs `du -sh /var/log/*` to identify largest files. |
| **11:26**  | Identifies `/var/log/inventory-service/app.log` at 31 GB and `/var/log/admin-dashboard/app.log` at 12 GB — neither has been rotated. |
| **11:27**  | Checks `logrotate` configuration: `/etc/logrotate.d/inventory-service` and `/etc/logrotate.d/admin-dashboard` configs are missing. These drop-in files should have been in place but are absent. |
| **11:28**  | Inventory Service begins logging: `ERROR: Unable to write to log file — No space left on device`. Admin Dashboard also reports write errors. |
| **11:28**  | Sarah Mitchell joins the bridge call. Incident severity confirmed at P3 (service degraded, not down). |
| **11:29**  | Carlos checks OS upgrade changelog. The OS upgrade on 2025-07-07 replaced `/etc/logrotate.d/` contents using the OS package defaults, overwriting any non-packaged drop-in files. |
| **11:30**  | Root cause confirmed: OS upgrade wiped application-specific logrotate configs. Logs have been accumulating for 7 days. |
| **11:31**  | Carlos manually compresses and archives old log segments: `gzip /var/log/inventory-service/app.log` — frees 29 GB. |
| **11:33**  | Disk usage drops to 18% on `/var/log`. Inventory Service and Admin Dashboard resume normal logging. |
| **11:35**  | Carlos recreates `/etc/logrotate.d/inventory-service` and `/etc/logrotate.d/admin-dashboard` from the team's configuration management repository (Ansible playbooks). |
| **11:37**  | Runs `logrotate --force /etc/logrotate.d/inventory-service` to verify the restored configuration works correctly. Rotation succeeds. |
| **11:39**  | Carlos checks all other application servers (`prod-app-01`, `prod-app-02`, `prod-app-04`) — confirms logrotate configs are intact on those hosts. Only `prod-app-03` was affected (was the only server upgraded in this patch cycle). |
| **11:40**  | Monitoring dashboards confirm `/var/log` at 18% and both services healthy. |
| **11:42**  | Incident declared resolved. Carlos documents findings. Post-mortem scheduled. |
| **14:00**  | Ansible playbook updated to assert logrotate drop-in configs are present after any OS upgrade task. |

---

## Root Cause Analysis

### Primary Root Cause
On 2025-07-07, `prod-app-03` underwent a scheduled OS minor version upgrade (`Ubuntu 22.04.3` → `22.04.4`). The OS package upgrade process replaced the contents of `/etc/logrotate.d/` with the package defaults. Application-specific logrotate drop-in files (`/etc/logrotate.d/inventory-service` and `/etc/logrotate.d/admin-dashboard`) were not managed by the OS package manager and were overwritten without warning. Without these configurations, `logrotate` ran nightly but silently skipped rotating the application logs, allowing them to grow unchecked for 7 days.

### Contributing Factors
- **Logrotate configs not in Ansible idempotency**: The Ansible playbook that manages the OS upgrade did not include a post-upgrade assertion to verify that application-specific logrotate configurations were present after the upgrade.
- **No disk usage trending alert**: The disk alert threshold was set at 90%, which was only triggered when the disk was nearly full. A warning at 70% would have provided earlier notice.
- **Post-upgrade verification checklist incomplete**: The post-OS-upgrade checklist included verifying service health and connectivity but did not include checking logrotate configuration presence.
- **7-day blind spot**: `logrotate` runs silently and its output is not monitored. It had been failing to rotate these logs for 7 days with no alert generated.

### Why Only `prod-app-03`?
`prod-app-03` was the only server in the fleet upgraded during the July 7 patch window. The other three application servers (`prod-app-01`, `02`, `04`) are scheduled for upgrade in the next patch cycle. This incident was caught before those upgrades, allowing the fix to be applied proactively.

---

## Impact Assessment

| Dimension          | Detail                                                                                        |
|--------------------|-----------------------------------------------------------------------------------------------|
| **User Impact**    | ~300 internal users of the Admin Dashboard experienced degraded functionality (slow/missing audit log writes) for approximately 4 minutes (11:28–11:33 UTC). |
| **Customer Impact**| Inventory Service degradation was internal/backend only. No customer-facing APIs were impacted. |
| **Data Impact**    | No log data was lost. The full 31 GB of unrotated Inventory Service logs was preserved and archived. No application data was corrupted. |
| **Revenue Impact** | None — affected services are internal tooling only.                                           |

---

## Resolution Steps

1. Identified the large unrotated log files via `du -sh /var/log/*`.
2. Confirmed the missing logrotate drop-in configuration files.
3. Correlated the missing configs with the OS upgrade performed on 2025-07-07.
4. Manually compressed the oversized log files to free disk space immediately.
5. Restored the logrotate drop-in configs from the Ansible configuration management repository.
6. Tested the restored configuration with `logrotate --force` to confirm correct behaviour.
7. Verified the other application servers in the fleet were not similarly affected.
8. Updated the Ansible OS upgrade playbook to assert logrotate configs post-upgrade.

---

## Lessons Learned

1. **OS upgrades can silently overwrite configuration files not managed by the package manager.** Any file dropped into a system-managed directory (like `/etc/logrotate.d/`) that is not tracked in the OS package must be managed via configuration management (Ansible/Chef/Puppet) with idempotency assertions run after every upgrade.
2. **Disk space trending alerts are more useful than threshold-only alerts.** A trending alert ("disk utilisation has grown by 5% per day for 3 consecutive days") would have caught this 3–4 days earlier.
3. **`logrotate` failures are silent by default.** Monitoring for `logrotate` exit codes or adding it to the infrastructure health dashboard would make failures visible.
4. **Post-upgrade checklists must cover configuration file integrity**, not just service health.
5. **Patch cycles should be staggered with a verification gate** — the fact that only one server was upgraded in this window limited the blast radius significantly.

---

## Action Items

| # | Action                                                                                              | Owner            | Due Date   | Ticket     |
|---|-----------------------------------------------------------------------------------------------------|------------------|------------|------------|
| 1 | Update Ansible OS upgrade playbook to assert all logrotate drop-in configs are present post-upgrade | Carlos Rivera    | 2025-07-18 | INFRA-5801 |
| 2 | Apply logrotate config verification to `prod-app-01/02/04` before their scheduled upgrade           | Carlos Rivera    | 2025-07-17 | INFRA-5802 |
| 3 | Add disk space trending alert: > 5%/day growth for 3 days triggers P3 alert                        | Sarah Mitchell   | 2025-07-21 | OBS-231    |
| 4 | Add disk space warning alert threshold at 70% (current is 90%)                                      | Sarah Mitchell   | 2025-07-18 | OBS-232    |
| 5 | Add `logrotate` execution monitoring to infrastructure health dashboard (check exit code nightly)   | Carlos Rivera    | 2025-07-25 | INFRA-5803 |
| 6 | Update post-OS-upgrade checklist to include logrotate config presence check                         | Sarah Mitchell   | 2025-07-21 | RUNBOOK-50 |
| 7 | Inventory all `/etc/logrotate.d/` drop-in files across the fleet and add to Ansible management      | Carlos Rivera    | 2025-07-31 | INFRA-5804 |

---

## Prevention Measures Implemented

- **Immediate**: Logrotate drop-in configs restored on `prod-app-03` and verified working.
- **Immediate**: Pre-emptive audit of `prod-app-01/02/04` confirmed their logrotate configs are intact.
- **Short-term**: Ansible OS upgrade playbook updated with post-upgrade assertion tasks for logrotate config presence.
- **Monitoring**: Disk space warning threshold lowered to 70%; disk trending alert (> 5%/day for 3 days) added to all production hosts.
- **Process**: Post-OS-upgrade runbook updated with a logrotate configuration integrity check as a mandatory step before signing off the upgrade.
