# FAILURES.md — System Failure Analysis & Technical Limitations

This document provides a realistic, honest technical analysis of failure modes where the LinkPlease Instagram automation system could still lose a DM, send a duplicate DM, or report incorrect metrics, along with existing mitigations and production recommendations.

---

## 1. Network Failure Between Outgoing API Request & Database Commit

* **Scenario**: The background worker claims a job and executes `POST /v1/dm/send`. PseudoGram processes the request, generates a `dm_id`, and sends the DM to the user. However, before the worker can write `job.status = 'waiting_reconciliation'` and execute `await session.commit()`, the server suffers a hard process crash, network disconnect, or SIGKILL.
* **Impact**: The database state for `job.status` remains `sending` or `queued`. Upon application restart, `recover_stuck_jobs()` resets the job to `queued`. The worker will pick up the job and re-issue `POST /v1/dm/send`.
* **Mitigation**: The system attaches a deterministic header `Idempotency-Key: dm-job-{job_id}` to every outgoing HTTP request. If the external PseudoGram API correctly enforces idempotency on this key, it returns the existing `dm_id` without re-sending the DM. If PseudoGram ignores the `Idempotency-Key` header, a **duplicate DM will be sent**.

---

## 2. Hard Worker Crash (SIGKILL / Out-Of-Memory) Mid-Execution

* **Scenario**: While the worker is processing an active batch of jobs, Render or Docker issues an ungraceful `SIGKILL` (e.g. host node migration or OOM kill).
* **Impact**: Jobs currently being processed are left in status `sending` in the database.
* **Mitigation**: On startup, `BackgroundWorker.recover_stuck_jobs()` queries for jobs in `sending` status and reverts them to `queued`. While no jobs are lost, any job killed post-API request suffers the risk described in Failure #1.

---

## 3. External API Soft-Hanging on HTTP 202 (Stuck Reconciliation)

* **Scenario**: The mock PseudoGram API returns `HTTP 202 Accepted` with `{ "dm_id": "dm_123", "status": "queued" }`. However, PseudoGram's internal worker silently drops the task or hangs indefinitely. Subsequent polling via `GET /v1/dm/{dm_id}` continues to return `status: queued` forever.
* **Impact**: The DM job remains permanently in status `waiting_reconciliation`. In `/stats`, this job is permanently counted under `queued`, and never transitions to `sent` or `failed`.
* **Mitigation**: Production systems require a TTL (Time-To-Live) reconciliation window (e.g. 24 hours). If `waiting_reconciliation` exceeds 24 hours, automatically mark the job as `failed` with `last_error = "reconciliation_timeout"`.

---

## 4. Database Connection Pool Exhaustion under Extreme Load Burst

* **Scenario**: A sudden burst of 1,000 concurrent webhook events hits `/webhook`. If the database pool max connection limit (e.g. 20 connections) is saturated and async timeouts elapse before acquiring a connection, database queries will throw `TimeoutError` or `ConnectionRefusedError`.
* **Impact**: `/webhook` calls fail with `HTTP 500`. The webhook sender (Instagram/PseudoGram) must retry the webhook delivery.
* **Mitigation**: Use an external connection pooler such as **PgBouncer**, configure SQLAlchemy pool size and overflow limit appropriately (`pool_size=20`, `max_overflow=30`), or enqueue raw HTTP payloads to a persistent disk buffer before DB ingestion.

---

## 5. Out-of-Order Deletion (`comment.deleted` After Delivery)

* **Scenario**: A user comments "PRICE", the worker rapidly processes the job, sends the DM, and marks status as `delivered`. 10 seconds later, the user deletes the comment, generating a `comment.deleted` webhook event.
* **Impact**: The deletion event arrives after the DM has already been delivered. Because the Instagram / PseudoGram API does not provide an "unsend DM" endpoint, the DM remains delivered.
* **Mitigation**: The system handles `comment.deleted` for any pending/queued jobs by transitioning them to `blocked`. However, once delivered, external state cannot be reversed.
