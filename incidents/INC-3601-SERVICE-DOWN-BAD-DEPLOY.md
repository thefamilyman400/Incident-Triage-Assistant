# Post-Mortem: INC-3601 — Payment Service Down (Bad Environment Variable in Deployment)

---

## Incident Metadata

| Field               | Value                                                      |
|---------------------|------------------------------------------------------------|
| **Incident ID**     | INC-3601                                                   |
| **Date**            | 2025-07-22                                                 |
| **Severity**        | P1 (Critical)                                              |
| **Status**          | Resolved                                                   |
| **Duration**        | 12 minutes (16:03 – 16:15 UTC)                             |
| **Affected Services** | Payment Service, Checkout Flow, Order Confirmation Service |
| **On-Call Engineer** | Yuki Tanaka (Payments Engineering)                        |
| **Incident Commander** | Priya Anand (Engineering Manager)                       |
| **Postmortem Author** | Yuki Tanaka                                              |
| **Review Date**     | 2025-07-24                                                 |

---

## Executive Summary

At 16:03 UTC on July 22, 2025, the Payment Service became completely unavailable immediately following a scheduled deployment of v4.2.0, causing all checkout and payment flows to fail with HTTP 500 errors. The root cause was a misconfigured environment variable in the Kubernetes deployment manifest: the `PAYMENT_GATEWAY_URL` variable was set to an internal staging endpoint rather than the production gateway URL, causing the service to crash on startup when it could not establish a connection to the payment processor. The incident was resolved in 12 minutes via an immediate rollback to v4.1.8, making this the shortest P1 incident in the team's recent history.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| **15:55**  | Deployment of `payment-service` v4.2.0 initiated via the CI/CD pipeline during the approved change window. Deployment includes a new retry logic feature for failed transactions. |
| **16:00**  | Kubernetes rolling update completes. New pods report `Running` status. |
| **16:02**  | Payment Service readiness probe returns healthy. Deployment pipeline marks release as successful. |
| **16:03**  | PagerDuty fires simultaneously: Payment Service error rate 100%, Checkout Flow error rate 100%. Yuki Tanaka paged. Customer Support receives first user complaints via chat. |
| **16:04**  | Yuki acknowledges. Priya Anand joins the incident bridge. Incident declared P1 immediately given payment flow impact. |
| **16:04**  | Status page updated: "We are investigating an issue affecting the checkout and payment flow." |
| **16:05**  | Yuki checks Payment Service pod logs: `FATAL: Unable to connect to payment gateway at https://staging-gateway.internal.acme.com/v2/process — connection refused`. |
| **16:05**  | Immediately identifies the issue: `PAYMENT_GATEWAY_URL` in the Kubernetes deployment manifest is pointing to the staging gateway, not production. |
| **16:06**  | Checks the deployment manifest diff in the release PR. Confirms: in a recent infrastructure refactor, the `payment-service` Helm values file had a staging-specific override (`PAYMENT_GATEWAY_URL: https://staging-gateway.internal.acme.com/v2/process`) that was accidentally left in and not overridden by the production values file. |
| **16:06**  | Root cause confirmed. Decision: roll back to v4.1.8 immediately rather than pushing a config hotfix (rollback is faster and lower risk). |
| **16:07**  | Rollback initiated: `kubectl rollout undo deployment/payment-service`. |
| **16:09**  | v4.1.8 pods come online. Payment Service logs show successful connection to the production payment gateway. |
| **16:10**  | Checkout Flow error rate drops to 0%. Order Confirmation Service recovers. |
| **16:11**  | Yuki confirms via Stripe dashboard that no payments are stuck in an errored state from the 8-minute window. |
| **16:13**  | All services healthy. Status page updated: "This issue has been resolved." |
| **16:15**  | Incident declared resolved. Post-mortem scheduled. Engineering leadership notified. |
| **17:40**  | Hotfix PR for the Helm values misconfiguration reviewed, approved, and merged. |
| **18:05**  | Payment Service v4.2.1 (with corrected config) deployed successfully. No issues. |

---

## Root Cause Analysis

### Primary Root Cause
The `payment-service` Helm chart was recently refactored to support multi-environment deployments. During this refactor, a staging-specific override for `PAYMENT_GATEWAY_URL` was added to `values-staging.yaml`. However, `values-production.yaml` was not updated to explicitly override this variable back to the production endpoint. Since Helm merges values files in order, and the staging override was inadvertently left in the base `values.yaml`, the production deployment inherited the staging `PAYMENT_GATEWAY_URL` value.

```yaml
# values.yaml (base) — should NOT contain environment-specific URLs
env:
  PAYMENT_GATEWAY_URL: "https://staging-gateway.internal.acme.com/v2/process"  # ← BUG: staging URL in base values

# values-production.yaml — missing the required override
# PAYMENT_GATEWAY_URL was not defined here, so the base value was inherited
```

The Payment Service application code performed a startup connection validation to the payment gateway, causing a `FATAL` error and immediate crash when the staging endpoint was unreachable from the production network.

### Contributing Factors
- **No environment variable validation in CI**: The CI pipeline did not include a step to validate that production Helm values contain required production-specific overrides.
- **Helm values refactor was not thoroughly reviewed**: The PR that introduced the multi-environment Helm refactor was reviewed for correctness of structure but the specific values override hierarchy was not checked against every deployment target.
- **Readiness probe did not catch the misconfiguration**: The Kubernetes readiness probe checks HTTP `/health` endpoint availability, but the health endpoint returned 200 even though the gateway URL was wrong (the connection attempt is async and happens at request time, not startup validation in the health check). *(Note: The `FATAL` crash on startup happened during the first actual payment request, not during the readiness probe.)*
- **Staging and production environments share a common Helm chart base**: This is a correct architectural choice, but it creates risk when environment-specific values are placed in the wrong file.

### Why Did the Readiness Probe Pass?
The Payment Service `/health` endpoint validates internal dependencies (database connectivity, configuration file presence) but does not make a live call to the external payment gateway. The gateway URL misconfiguration only manifested when the first actual payment request was processed after the deployment completed.

---

## Impact Assessment

| Dimension          | Detail                                                                                     |
|--------------------|--------------------------------------------------------------------------------------------|
| **User Impact**    | 100% of users attempting checkout during the 8-minute outage window (16:03–16:10 UTC) received payment failures. Estimated 640 failed checkout attempts. |
| **Revenue Impact** | Estimated $52,000 in checkout revenue deferred (not lost — users were able to retry after recovery; no payment was captured for failed attempts). |
| **SLA Impact**     | P1 SLA breached. Customer notification and SLA credit review required for affected enterprise accounts. |
| **Data Impact**    | No data corruption. No payments were partially processed. The Stripe dashboard confirmed zero orphaned transaction records. |
| **Reputational Impact** | Customer Support received 47 complaint tickets during the incident window. Status page incident published. |

---

## Resolution Steps

1. Identified the crash cause immediately from pod logs: invalid `PAYMENT_GATEWAY_URL` pointing to staging.
2. Confirmed the misconfiguration in the Helm values file diff.
3. Initiated `kubectl rollout undo deployment/payment-service` to restore v4.1.8.
4. Verified service recovery via pod logs, Checkout Flow error rate, and Stripe dashboard.
5. Updated the status page once recovery was confirmed.
6. Opened a hotfix PR to correct `values.yaml` and `values-production.yaml`, reviewed and merged.
7. Deployed v4.2.1 with the corrected configuration.

---

## Lessons Learned

1. **Environment-specific configuration values must never appear in the base Helm `values.yaml`.** Base values should contain only defaults safe for all environments, or use clearly marked placeholder values.
2. **CI pipelines must validate Helm values for required production overrides** before allowing a production deployment to proceed.
3. **Readiness probes should, where practical, validate critical external integrations.** A startup probe that verifies the payment gateway URL is reachable would have prevented the rollout from completing and alerted before user traffic hit the broken pods.
4. **Fast rollback is a first-class incident response tool.** Resolving this in 12 minutes was only possible because the rollback process was well-practiced and the previous version was immediately available. Rollback drills should be part of team readiness.
5. **Post-refactor deployments carry higher risk.** Infrastructure refactors (like the Helm values restructure) should be flagged in the deployment checklist and given extra scrutiny on the first production deploy.

---

## Action Items

| # | Action                                                                                            | Owner             | Due Date   | Ticket     |
|---|---------------------------------------------------------------------------------------------------|-------------------|------------|------------|
| 1 | Move all environment-specific values out of `values.yaml` into `values-<env>.yaml` files         | Yuki Tanaka       | 2025-07-28 | INFRA-6101 |
| 2 | Add CI step: validate required production env vars are present in `values-production.yaml`        | DevOps Team       | 2025-07-31 | CICD-330   |
| 3 | Update Payment Service startup probe to perform a live connectivity check to `PAYMENT_GATEWAY_URL`| Yuki Tanaka       | 2025-08-04 | PAY-1142   |
| 4 | Add automated diff check: alert if staging URLs appear in production deployment manifests         | DevOps Team       | 2025-08-07 | CICD-331   |
| 5 | Conduct rollback drill for all P1-eligible services (quarterly cadence)                           | Priya Anand       | 2025-08-15 | ENG-5901   |
| 6 | Review and improve readiness probe coverage for all payment-critical services                     | Yuki Tanaka       | 2025-08-11 | PAY-1143   |
| 7 | Document incident in runbook: "Payment Service Down — Diagnostic Checklist"                       | Yuki Tanaka       | 2025-07-28 | RUNBOOK-55 |

---

## Prevention Measures Implemented

- **Immediate**: `values.yaml` corrected — staging URL removed. `values-production.yaml` now explicitly declares `PAYMENT_GATEWAY_URL`.
- **Immediate**: Payment Service v4.2.1 deployed successfully with corrected config.
- **Short-term**: CI pipeline step added to validate that `PAYMENT_GATEWAY_URL` and other critical production env vars are defined in `values-production.yaml` before any production deployment is permitted.
- **Short-term**: Payment Service startup probe updated to perform a connectivity validation against the configured gateway URL, blocking rollout if the endpoint is unreachable.
- **Process**: Helm values refactor checklist created; any PR modifying Helm values hierarchy requires a second review from a DevOps engineer familiar with the multi-environment merge order.
