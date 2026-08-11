# NETWORK LATENCY / PACKET LOSS — Incident Runbook

**Alert Name:** `NETWORK_LATENCY_HIGH` / `PACKET_LOSS_DETECTED`
**Severity:** P2 – High (P1 if packet loss > 5% or latency > 500ms)
**Owner:** Platform Operations Team / Network Engineering
**Last Updated:** 2024-11-14
**Version:** 2.5

---

## Alert Description

This alert fires when one or more of the following conditions are met on production hosts or between critical service endpoints:

- **RTT latency > 200ms** (rolling 5-minute average) to internal or external target
- **Packet loss > 1%** over a 5-minute window
- **TCP retransmit rate > 0.5%** on a production network interface
- **DNS resolution time > 500ms** for service discovery endpoints

**Alert Source:** Prometheus Blackbox Exporter + `node_network_*` metrics
**Notification Channel:** PagerDuty → `#ops-alerts` → `#network-ops`

---

## Immediate Actions

> ⚠️ Network issues can cause cascading failures across all dependent services. Assess blast radius quickly.

1. **Acknowledge the alert** in PagerDuty.
2. **Determine the scope** — is this one host, a rack, an availability zone, or all traffic?
   ```bash
   # Quick sanity check from the affected host
   ping -c 10 8.8.8.8
   ping -c 10 <internal-gateway-ip>
   ping -c 10 <db-host>
   ```
3. **Check if other services are reporting latency** — review Grafana dashboard:
   `https://grafana.internal/d/network-overview`
4. **Rule out a monitoring issue** — verify from a second host:
   ```bash
   ssh ops-user@<second-host> "ping -c 5 <affected-host>"
   ```
5. **Notify `#ops-war-room`** if the issue affects more than one host or if latency > 500ms.
6. **Check cloud provider status** (AWS / GCP / Azure) for regional incidents:
   - AWS: `https://health.aws.amazon.com`
   - GCP: `https://status.cloud.google.com`

---

## Diagnostic Commands

### Basic Connectivity and Latency
```bash
# ICMP round-trip time (10 packets, show statistics)
ping -c 10 -i 0.5 <target-host>

# Continuous ping with timestamps (useful for capturing intermittent drops)
ping -D -i 1 <target-host> | while read line; do echo "$(date '+%Y-%m-%d %H:%M:%S') $line"; done

# MTR — combines ping and traceroute, shows per-hop statistics
mtr --report --report-cycles 30 <target-host>
mtr --report --report-cycles 30 --tcp --port 443 <target-host>
```

### Traceroute — Identify the Failing Hop
```bash
# Standard ICMP traceroute
traceroute <target-host>

# TCP traceroute (more reliable when ICMP is filtered)
traceroute -T -p 443 <target-host>

# UDP traceroute
traceroute -U -p 33434 <target-host>

# Paris traceroute (avoids ECMP load balancing skew)
paris-traceroute <target-host>
```

### Network Interface Statistics
```bash
# Check NIC speed, duplex, and link state
ethtool eth0
ip link show eth0

# Interface-level packet/error/drop counters
ip -s link show eth0

# Watch interface stats in real time
watch -n 2 "ip -s link show eth0 | grep -A4 'RX\|TX'"

# Check for NIC errors (dropped packets, overruns, errors)
ifconfig eth0
cat /proc/net/dev | column -t
```

### TCP Connection and Socket Analysis
```bash
# Overall TCP connection states
ss -s

# All established TCP connections with process info
ss -tnp state established

# View connections to a specific remote host
ss -tnp dst <target-ip>

# Check for TIME_WAIT accumulation (can exhaust ephemeral ports)
ss -tan | awk '{print $1}' | sort | uniq -c | sort -rn

# View TCP retransmit counters
ss -tin | grep -i retrans

# netstat alternative (if ss not available)
netstat -an | awk '{print $6}' | sort | uniq -c | sort -rn
```

### DNS Diagnostics
```bash
# Basic DNS resolution time
time dig <hostname>

# Detailed DNS query trace
dig +trace <hostname>

# Query a specific DNS server
dig @<dns-server-ip> <hostname>

# Check /etc/resolv.conf for correct nameservers
cat /etc/resolv.conf

# Test all configured nameservers
for ns in $(grep nameserver /etc/resolv.conf | awk '{print $2}'); do
  echo -n "Testing $ns: "
  time dig @$ns <hostname> A +short 2>&1 | tail -1
done

# Check systemd-resolved status (if in use)
systemd-resolve --status
resolvectl statistics
```

### Bandwidth and Throughput
```bash
# Real-time bandwidth per interface
iftop -i eth0 -n -P

# Or using nload
nload eth0

# Check for interface saturation (errors appear when NIC is overloaded)
sar -n DEV 5 12

# Test raw throughput between two hosts (requires iperf3 on both ends)
# On the server host:
iperf3 -s -p 5201
# On the client host:
iperf3 -c <server-ip> -p 5201 -t 30 -P 4
```

### Kernel Network Buffers and Tuning
```bash
# View current socket buffer sizes
sysctl net.core.rmem_max net.core.wmem_max
sysctl net.ipv4.tcp_rmem net.ipv4.tcp_wmem

# Check if TCP retransmit is elevated
cat /proc/net/snmp | grep -i retrans
netstat -s | grep -i "retransmit\|failed\|reset"

# Check conntrack table (full table = new connections dropped)
sudo conntrack -C
sysctl net.netfilter.nf_conntrack_max
sysctl net.netfilter.nf_conntrack_count
```

### Cloud / Overlay Network (AWS VPC / Kubernetes CNI)
```bash
# AWS: Check VPC flow logs for dropped packets
# (Via AWS Console: VPC → Flow Logs, or CloudWatch Logs Insights)

# Kubernetes: Check pod-to-pod connectivity
kubectl exec -it <pod-name> -n production -- ping <target-pod-ip>

# Check CNI plugin health (Calico example)
kubectl get pods -n kube-system | grep calico
kubectl logs -n kube-system <calico-node-pod> --tail=50

# Check node network conditions
kubectl describe node <node-name> | grep -A10 "Conditions"

# View network policies that may be blocking traffic
kubectl get networkpolicies -n production
```

---

## Common Root Causes

| # | Root Cause | Indicators |
|---|-----------|------------|
| 1 | Upstream ISP / cloud provider regional issue | Multiple hosts affected; cloud status page shows incident |
| 2 | NIC hardware error or duplex mismatch | `ethtool` shows half-duplex or errors; `/proc/net/dev` shows drops |
| 3 | Network congestion / bandwidth saturation | High `iftop` readings; NIC TX/RX near rated capacity |
| 4 | DNS resolution failure or slow nameserver | `dig` shows high latency; `dig +trace` fails mid-chain |
| 5 | Firewall / security group rule change | Traceroute drops at a specific hop; recent firewall change log |
| 6 | conntrack table exhaustion | New connections dropped; `nf_conntrack_count` near max |
| 7 | MTU mismatch (common in VPN/tunnel setups) | Large packets dropped; ping succeeds but data transfers fail |

---

## Resolution Steps

### Cause 1 — ISP / Cloud Provider Outage
```bash
# Confirm via status page and MTR — if the drop is at the provider edge:
mtr --report <target-host>

# If using AWS, check if failover to another region/AZ is possible
# Trigger Route 53 failover routing policy if configured
aws route53 change-resource-record-sets --hosted-zone-id <zone-id> \
  --change-batch file://failover-change.json

# Engage cloud provider support with the MTR report as evidence
```

### Cause 2 — NIC Error / Duplex Mismatch
```bash
# Force NIC speed and duplex (temporary — requires hardware team confirmation)
sudo ethtool -s eth0 speed 1000 duplex full autoneg off

# If NIC errors are hardware-related, schedule host maintenance/replacement
# Migrate workloads to a healthy host first
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
```

### Cause 3 — Bandwidth Saturation
```bash
# Identify top bandwidth consumers
sudo iftop -i eth0 -n -P -t -s 30 2>/dev/null | head -40

# Apply traffic shaping / QoS if applicable (tc command)
# Or identify and throttle the bulk data transfer process
ionice -c 3 -p <pid>   # lower I/O priority of offending process
renice +10 <pid>       # lower CPU scheduling priority
```

### Cause 4 — DNS Issues
```bash
# Temporarily add a working nameserver
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf

# Flush DNS cache
sudo systemd-resolve --flush-caches
# or
sudo service nscd restart

# If internal DNS (bind/unbound) is down, restart it
sudo systemctl restart bind9
sudo systemctl restart unbound
```

### Cause 5 — Firewall / Security Group
```bash
# Review recent iptables changes
sudo iptables -L -n -v --line-numbers
sudo iptables-save | diff - /etc/iptables/rules.v4.backup

# Roll back a bad iptables rule
sudo iptables -D <CHAIN> <line-number>

# In AWS: review Security Group change history in CloudTrail
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=AuthorizeSecurityGroupIngress \
  --start-time $(date -d '2 hours ago' --iso-8601=seconds)
```

### Cause 6 — conntrack Table Exhaustion
```bash
# Confirm
sysctl net.netfilter.nf_conntrack_count
sysctl net.netfilter.nf_conntrack_max

# Temporary fix: increase the table size
sudo sysctl -w net.netfilter.nf_conntrack_max=1048576

# Persist the change
echo "net.netfilter.nf_conntrack_max = 1048576" | sudo tee -a /etc/sysctl.d/99-conntrack.conf
sudo sysctl -p /etc/sysctl.d/99-conntrack.conf
```

### Cause 7 — MTU Mismatch
```bash
# Test with progressively smaller packet sizes to find MTU ceiling
ping -M do -s 1472 <target-host>   # 1500 byte total (1472 + 28 header)
ping -M do -s 1400 <target-host>
ping -M do -s 1200 <target-host>

# Set interface MTU to match the path MTU
sudo ip link set dev eth0 mtu 1400

# For VPN/tunnel interfaces, check inner vs. outer MTU settings
```

---

## Escalation Criteria

Escalate to **Network Engineering / Cloud Infrastructure (P1)** if:

- Latency > **500ms** or packet loss > **5%** and persists for more than **10 minutes**
- Issue affects **an entire availability zone or region**
- Root cause traceback points to **cloud provider infrastructure** (not our hosts)
- MTR or traceroute shows consistent drop at **provider edge or backbone hop**
- **Multiple services** are simultaneously experiencing degradation
- Issue cannot be identified within **20 minutes**

**Escalation Path:**
1. On-call SRE → `#network-ops` (immediate)
2. Network Engineering Lead (PagerDuty: `network-lead-oncall`)
3. Cloud provider TAM/Support (P1 ticket with MTR output attached)
4. VP Engineering if customer SLA breach is imminent

---

## Past Similar Incidents

| Incident ID | Date | Scope | Root Cause | Resolution Time |
|-------------|------|-------|-----------|-----------------|
| INC-4867 | 2024-10-14 | prod-api cluster | AWS us-east-1 transit gateway degradation — confirmed AWS incident | 1 hr 5 min |
| INC-4711 | 2024-09-05 | prod-db-01 | conntrack table exhausted under heavy microservice fan-out load | 35 min |
| INC-4480 | 2024-07-01 | prod-worker-* | Bad iptables rule deployed via Ansible — blocked port 5432 | 22 min |
| INC-4209 | 2024-05-02 | prod-app-02 | NIC duplex mismatch after ESXi host migration — half-duplex at 100Mbps | 50 min |
| INC-3874 | 2024-02-09 | all production | Internal DNS server (bind9) OOM-killed — all service discovery failed | 40 min |

---

## Related Alerts

- `SERVICE_DOWN` — high latency causes health check timeouts and service-down alerts
- `DB_REPLICATION_LAG` — network degradation between primary and replica increases lag
- `HIGH_CPU_USAGE` — network interrupt storms can spike CPU on `ksoftirqd`
- `DNS_RESOLUTION_FAILURE` — may trigger alongside or as a consequence of this alert
- `TLS_CERTIFICATE_EXPIRY` — occasionally misdiagnosed as a network issue; rule out first

---

## Notes

- **MTR output is the single most useful artefact** for diagnosing network path issues. Always run `mtr --report --report-cycles 30 <target>` and save the output before escalating.
- ICMP is frequently rate-limited or deprioritised by routers — use `--tcp` mode in mtr for more accurate results to HTTP endpoints.
- In AWS VPC environments, Security Group and NACL rules are stateless/stateful respectively — check both when debugging dropped connections.
- Always correlate with the Grafana network dashboard before concluding root cause. A single host's view can be misleading.
- When engaging cloud provider support, provide: MTR output, affected IP ranges, approximate start time (UTC), and CloudWatch/Stackdriver metrics link.
