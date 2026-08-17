"""
test_assignment.py -- End-to-end assignment verification script

Exercises every requirement from the assignment spec and prints a clear
PASS/FAIL report. Requires the backend to be running on localhost:8000.

Usage:
    python scripts/test_assignment.py [--url http://localhost:8000]
"""
import sys
import asyncio
import time
import json
import argparse
import httpx

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

DEFAULT_URL = "http://localhost:8000"

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results: list[tuple[str, str]] = []


def check(label: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((status, label))
    icon = "✅" if condition else "❌"
    print(f"  {icon} {label}" + (f" — {detail}" if detail else ""))

# ─────────────────────────────────────────────────────────────────────────────

async def run(base_url: str):
    print(f"\n{'═'*65}")
    print(f"  LinkPlease Assignment — End-to-End Verification")
    print(f"  Target: {base_url}")
    print(f"{'═'*65}\n")

    async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as client:

        # ── 0. Health check ──────────────────────────────────────────────
        print("── [0] Health Check")
        resp = await client.get("/health")
        check("GET /health returns 200", resp.status_code == 200)
        body = resp.json()
        check("Health response has 'status' field", "status" in body)

        # ── 1. Create rule ───────────────────────────────────────────────
        print("\n── [1] Rule Creation")
        resp = await client.post("/rules", json={
            "keyword": "ASSIGNTEST",
            "dm_message": "Thanks for your interest! Here is the info."
        })
        check("POST /rules returns 201", resp.status_code == 201)
        rule = resp.json()
        check("Response has rule_id", "rule_id" in rule)
        check("Response has keyword", rule.get("keyword") == "ASSIGNTEST")
        check("Response has dm_message", "dm_message" in rule)
        rule_id = rule.get("rule_id", "")

        # ── 2. Reject bad rules ──────────────────────────────────────────
        print("\n── [2] Rule Validation")
        resp = await client.post("/rules", json={"keyword": "", "dm_message": "test"})
        check("Empty keyword rejected (4xx)", resp.status_code >= 400)

        resp = await client.post("/rules", json={"keyword": "TEST", "dm_message": ""})
        check("Empty dm_message rejected (4xx)", resp.status_code >= 400)

        # ── 3. Valid webhook ─────────────────────────────────────────────
        print("\n── [3] Webhook Ingestion")
        t0 = time.perf_counter()
        resp = await client.post("/webhook", json={
            "event_id": "evt_assign_001",
            "event_type": "comment.created",
            "sent_at": "2026-08-10T09:14:22.481Z",
            "data": {
                "comment_id": "cmt_assign_001",
                "post_id": "post_assign_01",
                "text": "ASSIGNTEST please",
                "created_at": "2026-08-10T09:14:21.900Z",
                "from": {"user_id": "usr_assign_001", "username": "tester_a"}
            }
        })
        elapsed = time.perf_counter() - t0
        check("POST /webhook returns 200", resp.status_code == 200)
        check(f"Webhook responds within 5s ({elapsed:.2f}s)", elapsed < 5.0)
        check("Response has event_id", "event_id" in resp.json())

        # ── 4. Duplicate event_id blocked ────────────────────────────────
        print("\n── [4] Event Idempotency (duplicate event_id)")
        resp = await client.post("/webhook", json={
            "event_id": "evt_assign_001",  # same event_id
            "event_type": "comment.created",
            "sent_at": "2026-08-10T09:14:22.481Z",
            "data": {
                "comment_id": "cmt_assign_001b",
                "post_id": "post_assign_01",
                "text": "ASSIGNTEST again",
                "created_at": "2026-08-10T09:14:22.900Z",
                "from": {"user_id": "usr_assign_002", "username": "tester_b"}
            }
        })
        check("Duplicate event_id returns 200 (idempotent)", resp.status_code == 200)
        check("Response notes duplicate", "duplicate" in resp.json().get("message", "").lower())

        # ── 5. Same user, multiple comments — one DM ────────────────────
        print("\n── [5] Business Idempotency (same user, same rule → 1 DM)")
        for i in range(3):
            await client.post("/webhook", json={
                "event_id": f"evt_assign_dup_user_{i}",
                "event_type": "comment.created",
                "sent_at": "2026-08-10T09:15:00.000Z",
                "data": {
                    "comment_id": f"cmt_assign_dup_{i}",
                    "post_id": "post_assign_01",
                    "text": f"ASSIGNTEST — attempt {i}",
                    "created_at": "2026-08-10T09:15:00.000Z",
                    "from": {"user_id": "usr_assign_dup", "username": "dup_user"}
                }
            })
        # Allow worker a moment
        await asyncio.sleep(1)
        stats_resp = await client.get("/stats")
        stats = stats_resp.json()
        check("duplicates_blocked > 0 after repeat comments", stats.get("duplicates_blocked", 0) > 0,
              f"duplicates_blocked={stats.get('duplicates_blocked')}")

        # ── 6. Different users — separate DMs each ───────────────────────
        print("\n── [6] Different Users — Each Gets a DM")
        for i in range(3):
            r = await client.post("/webhook", json={
                "event_id": f"evt_assign_multi_user_{i}",
                "event_type": "comment.created",
                "sent_at": "2026-08-10T09:16:00.000Z",
                "data": {
                    "comment_id": f"cmt_assign_mu_{i}",
                    "post_id": "post_assign_01",
                    "text": "ASSIGNTEST please",
                    "created_at": "2026-08-10T09:16:00.000Z",
                    "from": {"user_id": f"usr_unique_{i}", "username": f"unique_{i}"}
                }
            })
            check(f"User {i} webhook accepted (200)", r.status_code == 200)

        # ── 7. Non-matching comment — no DM ─────────────────────────────
        print("\n── [7] Non-Matching Comment")
        resp = await client.post("/webhook", json={
            "event_id": "evt_assign_nomatch",
            "event_type": "comment.created",
            "sent_at": "2026-08-10T09:17:00.000Z",
            "data": {
                "comment_id": "cmt_assign_nomatch",
                "post_id": "post_assign_01",
                "text": "great photo!",
                "created_at": "2026-08-10T09:17:00.000Z",
                "from": {"user_id": "usr_nomatch", "username": "nomatch_user"}
            }
        })
        check("Non-matching comment accepted (200)", resp.status_code == 200)

        # ── 8. comment.deleted ────────────────────────────────────────────
        print("\n── [8] comment.deleted Event")
        resp = await client.post("/webhook", json={
            "event_id": "evt_assign_delete",
            "event_type": "comment.deleted",
            "sent_at": "2026-08-10T09:18:00.000Z",
            "data": {
                "comment_id": "cmt_assign_001",
                "post_id": "post_assign_01",
                "text": "",
                "created_at": "2026-08-10T09:18:00.000Z",
                "from": {"user_id": "usr_assign_001", "username": "tester_a"}
            }
        })
        check("comment.deleted returns 200", resp.status_code == 200)

        # ── 9. Stats correctness ─────────────────────────────────────────
        print("\n── [9] Statistics")
        await asyncio.sleep(2)  # let worker catch up
        resp = await client.get("/stats")
        check("GET /stats returns 200", resp.status_code == 200)
        stats = resp.json()
        check("Stats has 'sent' field", "sent" in stats)
        check("Stats has 'failed' field", "failed" in stats)
        check("Stats has 'queued' field", "queued" in stats)
        check("Stats has 'duplicates_blocked' field", "duplicates_blocked" in stats)
        check("Stats fields are non-negative integers",
              all(isinstance(stats.get(k, -1), int) and stats.get(k, -1) >= 0
                  for k in ("sent", "failed", "queued", "duplicates_blocked")))
        print(f"\n    Current /stats: {json.dumps(stats, indent=6)}")

        # ── 10. Admin API ────────────────────────────────────────────────
        print("\n── [10] Admin API Endpoints")
        resp = await client.get("/api/rules")
        check("GET /api/rules returns 200", resp.status_code == 200)
        check("Rules list is a list", isinstance(resp.json(), list))

        resp = await client.get("/api/jobs")
        check("GET /api/jobs returns 200", resp.status_code == 200)
        check("Jobs list is a list", isinstance(resp.json(), list))

        resp = await client.get("/api/events")
        check("GET /api/events returns 200", resp.status_code == 200)
        check("Events list is a list", isinstance(resp.json(), list))
        check("Events list is non-empty (events were sent)", len(resp.json()) > 0)

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'═'*65}")
    print(f"  RESULTS")
    print(f"{'═'*65}")
    passed = sum(1 for s, _ in results if s == PASS)
    total  = len(results)
    for status, label in results:
        print(f"  {status}  {label}")
    print(f"\n  {passed}/{total} checks passed")
    if passed == total:
        print(f"\n  🎉 ALL CHECKS PASSED\n")
    else:
        failed = [(s, l) for s, l in results if s == FAIL]
        print(f"\n  ❌ {len(failed)} checks FAILED:")
        for s, l in failed:
            print(f"     • {l}")
        print()

# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkPlease end-to-end assignment test")
    parser.add_argument("--url", default=DEFAULT_URL, help="Backend base URL")
    args = parser.parse_args()
    asyncio.run(run(args.url))
