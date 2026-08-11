# Post-Mortem: INC-3301 — Application 503 Errors (Connection Pool Exhaustion)

---

## Incident Metadata

| Field               | Value                                              |
|---------------------|----------------------------------------------------|
| **Incident ID**     | INC-3301                                           |
| **Date**            | 2025-07-02                                         |
| **Severity**        | P2 (High)                                          |
| **Status**          | Resolved                                           |
| **Duration**        | 28 minutes (09:41 – 10:09 UTC)                     |
| **Affected Services** | User Profile Service, Notifications Service, API Gateway |
| **On-Call Engineer** | Lena Hoffmann (Backend Engineering)               |
| **Incident Commander** | Marcus Webb (SRE)                               |
| **Postmortem Author** | Lena Hoffmann                                    |
| **Review Date**     | 2025-07-04                                         |

---

## Executive Summary

At 09:41 UTC on July 2, 2025, the API Gateway began returning HTTP 503 errors at a rate exceeding 40% for requests routed to the User Profile Service. Investigation revealed that the service's database connection pool had been fully exhausted, leaving new requests unable to obtain a database connection. The root cause was a connection leak introduced in `user-profile-service` v3.1.2, deployed the previous evening, where a new code path failed to close database connections in an exception handler. The incident was resolved by rolling back the deployment and redeploying the fixed version, with a total customer-facing duration of 28 minutes.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| **09:38**  | `user-profile-service` v3.1.2 was deployed the previous evening (2025-07-01, 21:00 UTC) and has been running in production for ~12 hours. |
| **09:41**  | PagerDuty fires: API Gateway 503 error rate > 25% on `/api/v1/users/*` endpoints. Lena Hoffmann paged. |
| **09:43**  | Lena acknowledges and opens the incident bridge. Marcus Webb joins as Incident Commander. |
| **09:45**  | Lena checks the API Gateway logs — all 503s are `upstream connection refused` from `user-profile-service`. Other services healthy. |
| **09:46**  | Lena checks `user-profile-service` pod logs. Log tail shows: `HikariPool-1 - Connection is not available, request timed out after 30000ms`. |
| **09:47**  | HikariCP connection pool metrics in Grafana confirm: active connections = 50/50 (pool fully exhausted). Pool has been growing steadily since ~08:10 UTC. |
| **09:49**  | Lena checks recent deployments. `user-profile-service` v3.1.2 deployed at 21:00 UTC yesterday — the only change in the past 24 hours. |
| **09:51**  | Code diff for v3.1.2 reviewed. New preference-update feature adds a DB write; the `catch` block in `UserPreferenceRepository.updatePreferences()` exits without closing the `Connection` object in the exception path. |
| **09:53**  | Root cause confirmed: connection leak in the exception handler. Every failed preference update leaks one connection. |
| **09:55**  | Decision made to roll back to v3.1.1 immediately. Fix is straightforward but will take ~20 minutes to build, test, and deploy. Rollback is faster. |
| **09:57**  | Rollback initiated via the deployment pipeline. New pods with v3.1.1 start receiving traffic. |
| **10:02**  | All v3.1.2 pods terminated. Connection pool metrics show active connections dropping from 50 to 8. |
| **10:04**  | 503 error rate falls to 0%. API Gateway health checks green. Notifications Service (which depends on User Profile Service) recovers. |
| **10:06**  | Lena confirms all dependent services healthy. Monitoring dashboards green. |
| **10:07**  | Engineers begin working on the fix in `UserPreferenceRepository.updatePreferences()`. |
| **10:09**  | Incident declared resolved. Post-mortem scheduled. Customers notified via status page. |
| **12:45**  | Fixed version (`v3.1.3`) deployed after full test cycle. Incident fully closed. |

---

## Root Cause Analysis

### Primary Root Cause
`user-profile-service` v3.1.2 introduced a new user preference update feature. In `UserPreferenceRepository.updatePreferences()`, the code acquired a database `Connection` object from HikariCP and used it in a try/catch block. In the nominal path the connection was correctly closed. However, in the exception-handling path (triggered when the upstream preference validation service returned an error), the method returned early without calling `connection.close()`. This caused the connection to remain open and checked out of the pool indefinitely.

```java
// BUGGY CODE (v3.1.2) — connection not closed in catch block
public void updatePreferences(String userId, Map<String, Object> prefs) {
    Connection conn = dataSource.getConnection();
    try {
        // ... write logic ...
    } catch (ValidationException e) {
        log.error("Validation failed for user {}", userId, e);
        return; // <-- connection never closed here
    }
    conn.close();
}
```

The validation service began returning errors at a higher rate (~8%) during a morning traffic peak at ~08:10 UTC, slowly draining the 50-connection pool over 90 minutes until it was fully exhausted at ~09:41 UTC.

### Contributing Factors
- **No connection pool monitoring alert**: HikariCP pool utilisation was not in the alerting configuration. The slow drain went unnoticed for 90 minutes.
- **Low validation error rate in testing**: In the test environment, the preference validation service mock always returns success. The exception path was never exercised under load.
- **Pool size not reviewed during code review**: The connection pool is configured to a max of 50 connections. No reviewer considered the impact of a leaky connection under sustained traffic.
- **12-hour gap before impact**: The leak was gradual enough that the deployment appeared healthy in the post-deploy monitoring window (30 minutes), which delayed association with the deployment.

---

## Impact Assessment

| Dimension          | Detail                                                                       |
|--------------------|------------------------------------------------------------------------------|
| **User Impact**    | ~5,800 users received 503 errors on profile-related operations (viewing/updating user settings, notification preferences). |
| **Service Impact** | User Profile Service: fully unavailable for ~7 minutes (10:02–10:04 effective recovery). API Gateway error rate peaked at 43%. Notifications Service: degraded for 15 minutes. |
| **Revenue Impact** | Minimal direct revenue impact. No checkout or payment flows affected.        |
| **Data Impact**    | No data loss. Partial preference updates during the degraded window were rolled back by the DB transaction. |

---

## Resolution Steps

1. Correlated 503 errors to `user-profile-service` via API Gateway upstream logs.
2. Identified HikariCP pool exhaustion via Grafana HikariCP metrics dashboard.
3. Confirmed connection leak in the v3.1.2 code diff — exception handler missing `connection.close()`.
4. Initiated rollback to `user-profile-service` v3.1.1 via the CI/CD pipeline.
5. Verified pool drain and recovery of all dependent services.
6. Developed fix (`v3.1.3`) wrapping the connection in a try-with-resources block to guarantee closure in all paths.
7. Deployed `v3.1.3` after full QA cycle at 12:45 UTC.

---

## Lessons Learned

1. **Database connections must always be managed with try-with-resources** (or equivalent RAII patterns) to guarantee closure even in exception paths. Manual `.close()` calls are error-prone.
2. **Connection pool utilisation must be monitored and alerted on**. A slow drain over 90 minutes should have triggered a warning long before exhaustion.
3. **Post-deploy monitoring windows should include pool-level metrics**, not just error rates and latency.
4. **Exception paths must be covered by integration tests** that exercise realistic failure modes of downstream dependencies.
5. **A 30-minute post-deploy monitoring window may be insufficient** for detecting gradual resource leaks that only manifest under sustained traffic.

---

## Action Items

| # | Action                                                                                    | Owner             | Due Date   | Ticket     |
|---|-------------------------------------------------------------------------------------------|-------------------|------------|------------|
| 1 | Add PagerDuty alert: HikariCP pool utilisation > 80% for 5 minutes                        | Marcus Webb       | 2025-07-09 | OBS-224    |
| 2 | Mandate try-with-resources for all JDBC Connection usage — add to coding standards doc     | Lena Hoffmann     | 2025-07-11 | ENG-5610   |
| 3 | Add static analysis rule (SonarQube) to detect unclosed JDBC connections                   | Yusuf Adeyemi     | 2025-07-18 | ENG-5611   |
| 4 | Extend post-deploy monitoring dashboard to include connection pool utilisation per service  | Marcus Webb       | 2025-07-09 | OBS-225    |
| 5 | Add integration test for `updatePreferences()` exception path with mock validation failure | Lena Hoffmann     | 2025-07-11 | TEST-889   |
| 6 | Review all repository classes for manual `.close()` patterns — replace with try-with-resources | Yusuf Adeyemi | 2025-07-25 | ENG-5612   |

---

## Prevention Measures Implemented

- **Immediate**: `user-profile-service` rolled back to v3.1.1. Fixed version v3.1.3 deployed with `try-with-resources` wrapping.
- **Monitoring**: HikariCP pool utilisation alert added to all production services (> 80% for 5 min = P3, > 95% for 2 min = P2).
- **Code Quality**: SonarQube rule enabled for unclosed JDBC connections. Any open PR touching repository classes will now fail the quality gate if the pattern is detected.
- **Process**: Coding standards document updated with mandatory use of try-with-resources for all database connection management.
