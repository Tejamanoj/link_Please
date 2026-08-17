# LinkPlease Instagram Automation Backend

Production-quality, high-reliability backend for Instagram comment DM automation. Built for the LinkPlease Tech Intern Assignment.

---

## 1. Project Overview

The system ingests Instagram comment webhook events from the PseudoGram API. When a comment matches a configured keyword rule, the system asynchronously sends a Direct Message (DM) to the commenter via the PseudoGram API.

Key design focus: **Extreme reliability under duplicates, failures, rate limits, out-of-order events, and high traffic.**

---

## 2. Architecture & Design

The application is structured as a clean, highly reliable **Modular Monolith** using FastAPI and SQLAlchemy 2.0.

```
                                  +---------------------------------------+
                                  |         Mock PseudoGram API           |
                                  |    (https://pseudogram-api...)        |
                                  +-------------------+-------------------+
                                                      |
                                                      | Webhook Delivery (POST /webhook)
                                                      v
+---------------------------------------------------------------------------------------------------+
| LinkPlease Backend                                                                                |
|                                                                                                   |
|   +-----------------------+     HMAC SHA256     +---------------------------------------------+   |
|   | POST /webhook         | ----------------->  | Signature Verification                      |   |
|   +-----------------------+                     +----------------------+----------------------+   |
|                                                                        |                          |
|                                                                        v                          |
|                                                 +---------------------------------------------+   |
|                                                 | DB Event Ingestion (UNIQUE event_id)        |   |
|                                                 +----------------------+----------------------+   |
|                                                                        |                          |
|                                                                        v                          |
|   +-----------------------+                     +---------------------------------------------+   |
|   | Rule Engine & Job     | <------------------ | Keyword Matcher (Case-insensitive)         |   |
|   | Creation              |                     +---------------------------------------------+   |
|   +-----------+-----------+                                                                       |
|               |                                                                                   |
|               v                                                                                   |
|   +-------------------------------------------------------------------------------------------+   |
|   | Database Job Queue (dm_jobs) — UNIQUE(rule_id, user_id)                                  |   |
|   +---------------------------------------------+---------------------------------------------+   |
|                                                 |                                                 |
|                                                 v                                                 |
|                                 +-----------------------------------------------+                 |
|                                 | Async Background Worker & DB Rate Limiter     |                 |
|                                 | (Max 10 requests / rolling 60s)               |                 |
|                                 +---------------+-------------------------------+                 |
|                                                 |                                                 |
|                                                 v                                                 |
|                                 +-----------------------------------------------+                 |
|                                 | Outgoing DM Client (POST /v1/dm/send)         |                 |
|                                 | Idempotency-Key: dm-job-{job_id}              |                 |
|                                 +-----------------------------------------------+                 |
+---------------------------------------------------------------------------------------------------+
```

---

## 3. Technology Stack

* **Language**: Python 3.11+
* **Framework**: FastAPI
* **ORM & Database**: SQLAlchemy 2.0 (Async Engine), PostgreSQL (Production), SQLite / aiosqlite (Local Dev & Testing)
* **Validation & Settings**: Pydantic v2 & Pydantic-Settings
* **HTTP Client**: `httpx.AsyncClient`
* **Test Suite**: pytest, pytest-asyncio
* **Deployment**: Docker, Render-compatible (`render.yaml`)

---

## 4. Database Schema

### `rules`
* `id` (VARCHAR, PK) — Unique rule identifier (e.g. `rule_a1b2c3d4e5f6`)
* `keyword` (VARCHAR, INDEX) — Keyword string (case-insensitive substring matching)
* `dm_message` (TEXT) — DM message content
* `created_at` (TIMESTAMPTZ) — Timestamp created

### `webhook_events`
* `id` (INTEGER, PK)
* `event_id` (VARCHAR, UNIQUE, INDEX) — Enforces unique webhook event delivery
* `event_type` (VARCHAR) — `comment.created`, `comment.deleted`
* `comment_id` (VARCHAR, INDEX)
* `post_id` (VARCHAR)
* `user_id` (VARCHAR, INDEX)
* `username` (VARCHAR)
* `text` (TEXT)
* `sent_at` (TIMESTAMPTZ)
* `status` (VARCHAR) — `received`, `processed`

### `dm_jobs`
* `id` (INTEGER, PK)
* `rule_id` (VARCHAR, FK -> rules.id)
* `user_id` (VARCHAR, INDEX)
* `comment_id` (VARCHAR, INDEX)
* `message` (TEXT)
* `status` (VARCHAR, INDEX) — `queued`, `sending`, `waiting_retry`, `waiting_reconciliation`, `delivered`, `failed`, `blocked`
* `attempts` (INTEGER)
* `dm_id` (VARCHAR, INDEX)
* `last_error` (TEXT)
* `next_retry_at` (TIMESTAMPTZ, INDEX)
* **Constraint**: `UNIQUE(rule_id, user_id)` — Guarantees only 1 DM per rule per user!

### `duplicate_blocks`
* `id` (INTEGER, PK)
* `rule_id` (VARCHAR)
* `user_id` (VARCHAR)
* `comment_id` (VARCHAR)
* `created_at` (TIMESTAMPTZ)

### `rate_limit_logs`
* `id` (INTEGER, PK)
* `timestamp` (TIMESTAMPTZ, INDEX)

---

## 5. Idempotency Strategy

The system tackles two distinct duplicate problems:

1. **Duplicate Webhook Events**: The database enforces a `UNIQUE` constraint on `webhook_events.event_id`. Concurrent or duplicate webhook deliveries fail DB insertion cleanly with `IntegrityError`, preventing duplicate processing.
2. **Same User Commenting Multiple Times**: The database enforces `UNIQUE(rule_id, user_id)` on `dm_jobs`. When a user comments multiple times matching the same rule, only the first attempt creates a `queued` job. Subsequent attempts trigger a database `IntegrityError`, recording a record in `duplicate_blocks` to maintain exact persistent statistics.

---

## 6. Retry & Backoff Strategy

* **HTTP 500 (Internal Error)**: Exponential backoff ($2^{\text{attempts}-1}$ seconds: 1s, 2s, 4s). Max 3 attempts (`MAX_DM_RETRIES`). After max attempts, job transitions to status `failed`.
* **HTTP 429 (Rate Limited)**: Reads `Retry-After` response header. Schedules `next_retry_at = NOW() + Retry-After`. Status set to `waiting_retry`.
* **HTTP 400 (Bad Request)**: Permanent failure. Job status set to `failed`.
* **HTTP 202 (Accepted)**: Stores `dm_id`. Job status set to `waiting_reconciliation`.

---

## 7. Rate Limiting Strategy

* Implements a database-backed **Sliding Window Rate Limiter** (`DMRateLimiter`).
* Tracks outgoing requests in `rate_limit_logs`.
* Guarantees outgoing DM requests strictly do not exceed **10 requests per rolling 60 seconds** across all background worker threads and server restarts.

---

## 8. Webhook Signature Verification

* Computes HMAC-SHA256 signature over raw request body using secret (`WEBHOOK_SECRET` or `PSEUDOGRAM_API_KEY`).
* Compares against `X-PseudoGram-Signature: sha256=<hex>` header using constant-time `hmac.compare_digest`.
* Rejects invalid or missing signatures with HTTP 401. Configurable via `VERIFY_WEBHOOK_SIGNATURE`.

---

## 9. Background Processing & Recovery

* Webhooks return HTTP 200 within <5 seconds after persisting event state.
* `BackgroundWorker` runs in async loop polling `dm_jobs` where `status IN ('queued', 'waiting_retry')`.
* Uses atomic database status transition (`status = 'sending'`) to safely claim jobs.
* On application startup, `recover_stuck_jobs()` recovers any jobs left in `sending` state due to process crashes.

---

## 10. DM Reconciliation (Part C)

* `BackgroundWorker.reconcile_pending_dms()` periodically polls `GET /v1/dm/{dm_id}` for jobs in `waiting_reconciliation`.
* When PseudoGram reports `status: delivered`, job is marked `delivered` (incrementing `sent` stats).
* If status is `failed`, retries or marks `failed`.

---

## 11. Local Setup

```bash
# 1. Clone repository & set up environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env file
cp .env.example .env

# 4. Run application
uvicorn app.main:app --reload --port 8000
```

---

## 12. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PSEUDOGRAM_API_KEY` | `""` | Mock API Key for PseudoGram |
| `PSEUDOGRAM_BASE_URL` | `https://pseudogram-api.onrender.com` | Base URL for PseudoGram API |
| `DATABASE_URL` | `sqlite+aiosqlite:///./linkplease.db` | SQLAlchemy Async DB Connection URL |
| `WEBHOOK_SECRET` | `""` | HMAC Secret (defaults to API key if empty) |
| `MAX_DM_RETRIES` | `3` | Maximum DM send retry attempts |
| `VERIFY_WEBHOOK_SIGNATURE` | `true` | Enable/Disable HMAC verification |

---

## 13. Running Tests

```bash
# Run complete test suite with verbose output
pytest -v
```

Tests cover:
- Rule creation & case-insensitive keyword matching
- Webhook signature verification, invalid payloads, duplicate `event_id`
- Idempotency for duplicate events & duplicate user comments
- External API mocking (202, 500, 429, 400 responses)
- Exponential backoff & `Retry-After` handling
- Sliding window rate limiting enforcement (10 req / 60s)
- Concurrent high volume load testing (200+ events)

---

## 14. API Examples

### Create Rule (`POST /rules`)
```bash
curl -X POST http://localhost:8000/rules \
  -H "Content-Type: application/json" \
  -d '{
    "keyword": "PRICE",
    "dm_message": "Here is the price list: http://example.com/pricing"
  }'
```
Response (201 Created):
```json
{
  "rule_id": "rule_a1b2c3d4e5f6",
  "keyword": "PRICE",
  "dm_message": "Here is the price list: http://example.com/pricing"
}
```

### Ingest Webhook (`POST /webhook`)
```bash
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-PseudoGram-Signature: sha256=<HMAC_HEX>" \
  -d '{
    "event_id": "evt_01J8ZQ4K2N7RXA",
    "event_type": "comment.created",
    "sent_at": "2026-08-10T09:14:22.481Z",
    "data": {
      "comment_id": "cmt_9f2a7c",
      "post_id": "post_44de1b",
      "text": "Can you send me the PRICE please?",
      "from": {
        "user_id": "usr_3b91fe",
        "username": "arjun.shoots"
      }
    }
  }'
```
Response (200 OK):
```json
{
  "status": "ok",
  "event_id": "evt_01J8ZQ4K2N7RXA",
  "message": "Event ingested (processed)"
}
```

### Get Statistics (`GET /stats`)
```bash
curl http://localhost:8000/stats
```
Response (200 OK):
```json
{
  "sent": 142,
  "failed": 3,
  "queued": 8,
  "duplicates_blocked": 57
}
```

---

## 15. Deployment Instructions

### Render Deployment
1. Connect GitHub repository to **Render**.
2. Render automatically detects `render.yaml`.
3. Set environment variables `PSEUDOGRAM_API_KEY`, `WEBHOOK_SECRET`, `DATABASE_URL` (PostgreSQL internal URL).
4. Deploy Service.

---

## 16. Explanation of Completion (Parts A, B & C)

* **Part A**: Core DB schema, rules API, webhook event persistence, rule matching engine, `(rule_id, user_id)` idempotency, background job queue, exponential backoff retries, `/stats` endpoint.
* **Part B**: HMAC-SHA256 raw body signature verification, persistent statistics calculation, database-backed 10 req/60s rate limiter, concurrent load safety.
* **Part C**: DM status reconciliation loop (`GET /v1/dm/{dm_id}`), `comment.deleted` event handling (cancels pending jobs), crash recovery on startup.
