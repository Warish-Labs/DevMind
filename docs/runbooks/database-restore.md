# Runbook: Database Point-In-Time Restore (PITR) & Recovery Drill

**Owner**: Engineering / Operations  
**Governing Documents**: [docs/10 §16, §21, §22](../10-deployment-and-operations.md), [ADR-046](../12-architecture-decisions-and-open-questions.md), [ADR-047](../12-architecture-decisions-and-open-questions.md)  
**Status**: Confirmed & Tested (Milestone 10, Task M10-06)

---

## 1. Overview & Recovery Objectives

| Metric | Target Objective | Validated Capability |
|---|---|---|
| **RPO (Recovery Point Objective)** | Maximum acceptable data loss window | Up to provider PITR retention window (Neon: 24h on Free tier, up to 30 days on paid). Storage snapshots and write-ahead log (WAL) permit restore to exact timestamp/LSN. |
| **RTO (Recovery Time Objective)** | Maximum acceptable restore & switchover duration | Target: **< 5 minutes** to provision scratch recovery branch, run Alembic head check, and re-point `DATABASE_URL`. Local schema & seed replay: **< 3 seconds**. |
| **Scope** | Disasters covered | Accidental destructive migration, corrupted embedding space, data corruption, hardware/datacenter loss, regional outage. |

---

## 2. Neon Serverless Architecture Context (ADR-046)

In Neon PostgreSQL serverless:
1. Compute and storage are separated. Storage is continuously written to a multi-tenant Paxos log.
2. A database restore is executed by **branching** the storage tree at a specific Point in Time (timestamp or Log Sequence Number - LSN).
3. The new branch immediately provisions a compute endpoint with the exact state of the database at that time, with **zero downtime or data impact** on the existing branch.

---

## 3. Step-by-Step Restoration Procedure

### Phase 1: Halt Ingestion & Mutating Background Work

To prevent in-flight writes while preparing the restore:
1. Activate emergency operational kill switches via environment variable or API:
   - `DEVMIND_KILL_SWITCH_INDEXING=true` (stops chunk/file upload and indexing)
   - `DEVMIND_KILL_SWITCH_PAUSE_QUEUES=true` (pauses Celery worker task processing)
2. Verify in Render / application logs that workers are idle:
   ```bash
   # Check worker health probe
   curl -s -f https://<devmind-api>/readyz/alerts
   ```

### Phase 2: Create Recovery Branch in Neon

1. Log into Neon Console or use the Neon CLI (`neonctl`):
   ```bash
   # Create a recovery branch from the target timestamp
   neonctl branches create \
     --project-id <NEON_PROJECT_ID> \
     --name "recovery-$(date +%Y%m%d%H%M%S)" \
     --parent main \
     --time "2026-10-25T04:00:00Z"
   ```
2. Retrieve the connection string for the new recovery branch:
   ```bash
   neonctl connection-string \
     --project-id <NEON_PROJECT_ID> \
     --branch "recovery-..." \
     --pooled
   ```

### Phase 3: Validate Recovery Branch & Alembic Schema

Before directing application traffic to the new branch:
1. Run migration verification from a local runner or staging container:
   ```bash
   DATABASE_URL="postgresql+psycopg://<user>:<password>@<ep-recovery-pooled>.neon.tech/neondb" \
     alembic current
   ```
2. Confirm the head revision matches `alembic heads`:
   - Expected head: `0010_retention_policies`
3. Execute table inventory validation query:
   ```sql
   SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';
   -- Expect 29 core DevMind tables
   ```

### Phase 4: Switchover & Application Reconnection

1. Update `DATABASE_URL` in Render environment settings:
   - Set `DATABASE_URL` to the pooled endpoint of the recovery branch.
2. Redeploy or restart the single Render Web Service container (`DEVMIND_RUN_MODE=all`):
   - At startup, the launcher disposes the old engine connection pool via `close_db_engine()`.
   - The async engine initializes a new pool (`pool_size=5`, `max_overflow=5`, `pool_pre_ping=True`).
3. Verify `/readyz` health and database connectivity:
   ```bash
   curl -s -i https://<devmind-api>/readyz
   # HTTP 200 OK {"status": "ok", "checks": {"database": "connected", "alembic": "head"}}
   ```

### Phase 5: Post-Restore Reconciliation & Job Sweep

Because the database was restored to an earlier point in time, in-flight jobs that were running at that timestamp must be reconciled:
1. Deactivate kill switches (`DEVMIND_KILL_SWITCH_PAUSE_QUEUES=false`, `DEVMIND_KILL_SWITCH_INDEXING=false`).
2. The Celery Beat scheduler automatically runs:
   - `devmind.stale_job_reaper` (every 60s): Reaps any jobs restored in `status='running'` whose worker heartbeat expired ($> 120\text{s}$), resetting them to `status='queued'` (if `attempt < max_attempts`) or `status='failed'`.
   - `devmind.enqueuer_sweep` (every 60s): Scans PostgreSQL for all stranded jobs in `status='queued'` and re-dispatches them to the Celery broker.
3. Validate queue health and error rates:
   ```bash
   curl -s https://<devmind-api>/readyz/alerts
   # Verify 0 critical alerts
   ```

---

## 4. Disaster Scenarios & Quick Actions

| Scenario | Immediate Action |
|---|---|
| **Accidental destructive migration** | Stop container. Branch Neon at timestamp 1 minute prior to migration. Run forward-fix or switch `DATABASE_URL`. |
| **Corrupted embedding space** | No DB restore required: trigger embedding space re-index via admin endpoint (`POST /api/v1/projects/{id}/reindex`). |
| **Redis complete data wipe** | No DB restore required: PostgreSQL is authoritative. The enqueuer sweep and stale job reaper rebuild queue state automatically within 60 seconds (docs/02 §11). |
| **Tenant accidental project deletion** | Restore database into scratch branch, export project data, and re-import via script. |

---

## 5. Automated Verification Test Suite

The database restore procedures, schema integrity, tenant isolation, and post-restore reconciliation are continuously validated in:
- [`server/tests/test_restore_drill.py`](../../server/tests/test_restore_drill.py)
