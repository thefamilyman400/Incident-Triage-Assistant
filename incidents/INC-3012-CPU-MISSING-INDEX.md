# Post-Mortem: INC-3012 — CPU Spike After Deployment (Missing DB Index)

---

## Incident Metadata

| Field               | Value                                          |
|---------------------|------------------------------------------------|
| **Incident ID**     | INC-3012                                       |
| **Date**            | 2025-06-18                                     |
| **Severity**        | P1 (Critical)                                  |
| **Status**          | Resolved                                       |
| **Duration**        | 52 minutes (14:07 – 14:59 UTC)                 |
| **Affected Server** | prod-db-02                                     |
| **Affected Services** | Customer Portal, Product Search API, Checkout Service |
| **On-Call Engineer** | James Cartwright (Backend Engineering)        |
| **Incident Commander** | Priya Anand (Engineering Manager)           |
| **Postmortem Author** | James Cartwright                             |
| **Review Date**     | 2025-06-20                                     |

---

## Executive Summary

At 14:07 UTC on June 18, 2025, a P1 incident was declared after CPU on `prod-db-02` spiked to 100% within minutes of a scheduled feature deployment to the Product Search API. The new feature introduced a database query that filtered on a non-indexed column in the `product_catalog` table, triggering full table scans on every search request. Under normal production load, this caused `prod-db-02` to become fully saturated, cascading into failures across the Customer Portal and Checkout Service. The incident was resolved by adding a database index via an emergency hotfix and verifying the fix under load, totalling 52 minutes of customer-facing impact.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| **13:55**  | Deployment of `product-search-api` v2.4.1 begins via the automated CI/CD pipeline. Canary release to 10% of traffic. |
| **14:00**  | Canary deployment completes. No immediate errors observed in Datadog. |
| **14:03**  | Full rollout promoted to 100% of traffic by the deployment pipeline. |
| **14:07**  | PagerDuty fires: `prod-db-02` CPU > 95%. Checkout Service error rate rises to 18%. James Cartwright paged. |
| **14:09**  | James acknowledges. Opens incident bridge. Incident Commander Priya Anand joins. |
| **14:11**  | James SSHes to `prod-db-02`. `SHOW PROCESSLIST` shows hundreds of identical queries in `Sending data` state, all against `product_catalog`. |
| **14:13**  | Query identified: `SELECT * FROM product_catalog WHERE supplier_id = ? AND category_tag = ?`. No index on `supplier_id` or `category_tag`. |
| **14:15**  | `EXPLAIN` confirms full table scan (type: `ALL`, rows: 18,400,000). Query is the new feature introduced in v2.4.1. |
| **14:17**  | Deployment correlation confirmed. Priya escalates to P1 and notifies stakeholders. Customer Support alerted. |
| **14:20**  | Decision: write an emergency hotfix to add the missing index rather than rolling back (rollback would remove the new feature; index can be added without downtime). |
| **14:22**  | Raj Patel (DBA) joins the bridge to supervise the index creation on a live production database. |
| **14:25**  | `CREATE INDEX idx_product_catalog_supplier_category ON product_catalog (supplier_id, category_tag);` executed using `ALGORITHM=INPLACE, LOCK=NONE` to avoid table lock. |
| **14:31**  | Index build in progress. CPU is still high but stable at ~92% — queries are queuing rather than crashing. |
| **14:45**  | Index creation completes. `EXPLAIN` now shows index range scan (type: `range`, rows: ~240). |
| **14:47**  | CPU on `prod-db-02` drops from 92% to 14% within 90 seconds. Checkout Service error rate falls to 0.1%. |
| **14:51**  | Customer Portal and Product Search API confirmed fully healthy. Monitoring dashboards green. |
| **14:55**  | Hotfix PR merged into `main` to add the index to the schema migration file for future deployments. |
| **14:59**  | Incident declared resolved. Post-mortem scheduled. Stakeholders notified via status page. |

---

## Root Cause Analysis

### Primary Root Cause
The `product-search-api` v2.4.1 release introduced a new product filtering feature that queried `product_catalog` using `supplier_id` and `category_tag` as filter predicates. Neither column was indexed. The `product_catalog` table contains approximately 18.4 million rows. Under production query load (~1,200 search requests/minute), each request triggered a full table scan, collectively saturating `prod-db-02` CPU to 100%.

### Contributing Factors
- **No database review in the PR**: The pull request for the new feature was reviewed only by application engineers. There was no mandatory DBA or database-focused review step in the PR checklist.
- **Canary phase too short**: The 10% canary ran for only 5 minutes before full rollout. CPU impact was not yet visible at 10% traffic.
- **No query performance test in CI**: The CI pipeline runs unit tests and integration tests against a test dataset of ~500 rows. Full table scan behaviour only manifests at production data volumes.
- **Missing schema migration review**: The feature's schema migration file was reviewed but the absence of an index was not flagged as an issue.

### Why Wasn't the Canary Sufficient?
At 10% traffic, the database handled approximately 120 search requests/minute. Each request was slow but the CPU stayed below the 90% alert threshold (~68% at canary load). The alert only fired after promotion to 100%.

---

## Impact Assessment

| Dimension          | Detail                                                                          |
|--------------------|---------------------------------------------------------------------------------|
| **User Impact**    | ~14,000 customers experienced degraded or failed searches during the 52-minute window. |
| **Revenue Impact** | Estimated $18,400 in lost Checkout revenue due to 18% error rate on the Checkout Service for ~12 minutes. |
| **Service Impact** | Customer Portal: severely degraded. Product Search API: p99 latency 12,000ms. Checkout Service: 18% error rate at peak. |
| **SLA Impact**     | Breached P1 SLA for Customer Portal (uptime commitment). Customer notification required. |
| **Data Impact**    | No data corruption or loss.                                                     |

---

## Resolution Steps

1. Correlated the CPU spike with the `product-search-api` v2.4.1 deployment timeline.
2. Used `SHOW PROCESSLIST` and `EXPLAIN` to identify the full table scan query.
3. Decided against rollback to preserve the new feature value; proceeded with emergency index creation.
4. Added composite index `(supplier_id, category_tag)` using `ALGORITHM=INPLACE, LOCK=NONE` to avoid downtime.
5. Verified CPU and query plan improvement post-index.
6. Merged hotfix to add the index to the tracked schema migration for future environment consistency.

---

## Lessons Learned

1. **All new queries on large tables must be reviewed with `EXPLAIN` against production-scale data before deployment.**
2. **Canary periods must be long enough to trigger meaningful load on dependent systems.** 5 minutes at 10% is insufficient for database CPU alerting to fire.
3. **PR checklists must include a mandatory database review gate** for any PR touching data access layers.
4. **CI/CD pipelines should include query plan analysis** (e.g., using `pt-query-advisor` or similar) against a representative dataset.
5. **Composite index strategy**: filtering on multiple columns should prompt consideration of composite indexes at design time, not after a production incident.

---

## Action Items

| # | Action                                                                              | Owner             | Due Date   | Ticket     |
|---|-------------------------------------------------------------------------------------|-------------------|------------|------------|
| 1 | Add mandatory DBA review to PR template for any data access layer changes           | Priya Anand       | 2025-06-25 | ENG-5501   |
| 2 | Extend canary phase minimum to 15 minutes before full rollout                       | DevOps Team       | 2025-06-27 | CICD-318   |
| 3 | Integrate `pt-query-advisor` into CI pipeline for schema/query changes              | James Cartwright  | 2025-07-04 | ENG-5502   |
| 4 | Provision a production-scale staging database for pre-release query testing         | Raj Patel         | 2025-07-11 | DB-901     |
| 5 | Document incident in runbook: "CPU Spike Post-Deployment" diagnostic steps          | James Cartwright  | 2025-06-24 | RUNBOOK-44 |
| 6 | Review all queries introduced in last 90 days for missing indexes on large tables   | Raj Patel         | 2025-06-30 | DB-902     |

---

## Prevention Measures Implemented

- **Immediate**: Composite index `idx_product_catalog_supplier_category` added to `prod-db-02` and to the schema migration baseline.
- **Process**: PR template updated to include a "Database Impact" section requiring DBA sign-off for any data layer changes.
- **Monitoring**: Added Datadog monitor for "queries with type=ALL (full scan) executing > 500ms on prod-db-*" with P1 auto-escalation.
- **Pipeline**: Canary promotion gate extended from 5 to 15 minutes, with an explicit CPU health check on `prod-db-02` before full rollout is permitted.
