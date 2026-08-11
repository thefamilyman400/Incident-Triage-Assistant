# INC-4201 — UCD Agent Offline (OOM Kill)

## Incident Summary
| Field | Value |
|---|---|
| Incident ID | INC-4201 |
| Severity | P2 |
| Status | Resolved |
| Duration | 47 minutes |
| Affected System | IBM UrbanCode Deploy agent on `prod-app-deploy-01` |
| Affected Deployments | 3 deployments queued for `PaymentService` and `OrderService` |
| Detection | PagerDuty alert — UCD agent `prod-app-deploy-01` status OFFLINE |
| On-Call Engineer | Platform Engineering |

## Timeline
| Time | Event |
|---|---|
| 14:32 | PagerDuty alert fires — UCD agent `prod-app-deploy-01` shows OFFLINE in UCD server |
| 14:34 | On-call engineer acknowledges alert, SSHs into `prod-app-deploy-01` |
| 14:35 | `ps aux` confirms no `ibm-ucd-agent` JVM process running |
| 14:36 | `agent.out` log reviewed — `java.lang.OutOfMemoryError: Java heap space` found at 14:29 |
| 14:37 | `dmesg` confirms OOM killer targeted the agent JVM process |
| 14:40 | Root cause confirmed: heap set to 256m default, exhausted during large WAR artifact staging |
| 14:43 | `agent.jvm.max.heap` increased to 512m in `installed.properties` |
| 14:44 | Agent restarted via `systemctl restart ibm-ucd-agent` |
| 14:46 | `agent.out` shows `Connected to server` — agent back ONLINE |
| 14:48 | 3 queued deployments resumed and completed successfully |
| 15:19 | Incident closed after 30-minute monitoring period with no recurrence |

## Root Cause Analysis
The UCD agent JVM on `prod-app-deploy-01` was configured with the default heap size of 256m (`agent.jvm.max.heap=256m`). During a scheduled deployment of `PaymentService v3.1.2`, the agent was asked to stage a 180MB WAR artifact and run pre-deployment validation scripts simultaneously. The combined memory footprint exceeded the 256m heap limit, triggering a `java.lang.OutOfMemoryError`. The Linux OOM killer subsequently terminated the JVM process, taking the agent offline.

**Contributing factors:**
- Default heap size was never reviewed during initial agent provisioning
- No JVM heap utilisation monitoring was in place
- No systemd `Restart=on-failure` configured — agent did not self-recover

## Impact Assessment
- 3 production deployments (`PaymentService`, `OrderService` x2) blocked for 47 minutes
- No end-user impact — deployments were scheduled maintenance window tasks
- Release manager notified of 47-minute deployment window delay

## Resolution Steps
1. SSH into `prod-app-deploy-01`
2. Confirmed OOM kill via `dmesg | grep -i "out of memory"`
3. Edited `/opt/ibm-ucd/agent/conf/agent/installed.properties`:
   - Changed `agent.jvm.max.heap=256m` → `agent.jvm.max.heap=512m`
4. Restarted agent: `systemctl restart ibm-ucd-agent`
5. Confirmed reconnection in `agent.out`: `Connected to server at <UCD_SERVER>:7918`
6. Manually triggered queued deployments from UCD UI

## Lessons Learned
1. The default 256m heap is insufficient for agents handling large artifacts (>100MB) — 512m should be the provisioning standard
2. No JVM heap monitoring was in place — the OOM was invisible until the agent died
3. `Restart=on-failure` in the systemd unit would have self-healed the agent within 30 seconds, avoiding the alert entirely
4. Agent provisioning Ansible playbook does not set heap size — it uses the installer default

## Action Items
| Action | Owner | Due Date |
|---|---|---|
| Update Ansible agent provisioning playbook to set `agent.jvm.max.heap=512m` | Platform Engineering | Sprint +1 |
| Add `Restart=on-failure` + `RestartSec=30` to `ibm-ucd-agent.service` unit | Platform Engineering | Sprint +1 |
| Add JVM heap utilisation alert (>80% threshold) via Prometheus JMX exporter | Observability Team | Sprint +2 |
| Audit all UCD agents for default heap setting and remediate | Platform Engineering | Sprint +1 |

## Prevention Measures
- Standardise `agent.jvm.max.heap=512m` across all agent provisioning (Ansible playbook updated)
- Enable systemd auto-restart for the agent service
- Add heap monitoring via JMX exporter + Prometheus alert rule

## Sources
- Runbook: `runbooks/UCD_AGENT_OFFLINE_RUNBOOK.md`
