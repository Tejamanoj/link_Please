"""
load_test.py -- LinkPlease 500-event stress test

Sends 500 webhook events to the running backend within ~10 seconds using
async concurrency. Includes duplicate events and duplicate users to exercise
all idempotency paths.

Usage:
    python scripts/load_test.py [--url http://localhost:8000] [--events 500]
"""
import sys
import asyncio
import time
import random
import string
import argparse
import json
import httpx

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# --- Config -----------------------------------------------------------------

DEFAULT_URL = "http://localhost:8000"

TOTAL_EVENTS = 500
CONCURRENCY = 15          # simultaneous requests in flight (optimal for SQLite file lock limit; PG scales higher)
DUPLICATE_RATE = 0.20     # 20% of events reuse an earlier event_id

DUPLICATE_USER_RATE = 0.30 # 30% of events reuse an earlier user_id
KEYWORD = "LOADTEST"
POST_ID = "post_loadtest_01"

# ─── Helpers ─────────────────────────────────────────────────────────────────

def rand_id(prefix: str, length: int = 8) -> str:
    return f"{prefix}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=length))}"

def make_event(event_id: str, user_id: str, username: str, comment_id: str, text: str) -> dict:
    return {
        "event_id": event_id,
        "event_type": "comment.created",
        "sent_at": "2026-08-10T09:14:22.481Z",
        "data": {
            "comment_id": comment_id,
            "post_id": POST_ID,
            "text": text,
            "created_at": "2026-08-10T09:14:21.900Z",
            "from": {
                "user_id": user_id,
                "username": username
            }
        }
    }

# ─── Core ────────────────────────────────────────────────────────────────────

async def send_event(client: httpx.AsyncClient, base_url: str, payload: dict,
                     results: list, sem: asyncio.Semaphore):
    async with sem:
        start = time.perf_counter()
        try:
            resp = await client.post(f"{base_url}/webhook", json=payload, timeout=10.0)
            elapsed = time.perf_counter() - start
            results.append({
                "status": resp.status_code,
                "elapsed": elapsed,
                "event_id": payload["event_id"]
            })
        except Exception as e:
            elapsed = time.perf_counter() - start
            results.append({"status": 0, "elapsed": elapsed, "error": str(e), "event_id": payload["event_id"]})

async def ensure_rule(base_url: str) -> str:
    """Create (or reuse) the load-test keyword rule."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{base_url}/rules", json={
            "keyword": KEYWORD,
            "dm_message": "Load test DM — automated."
        }, timeout=10.0)
        if resp.status_code == 201:
            rule_id = resp.json()["rule_id"]
            print(f"  ✅ Rule created: {rule_id}")
        else:
            print(f"  ⚠️  Rule creation returned {resp.status_code}: {resp.text[:120]}")
            rule_id = "unknown"
    return rule_id

async def run_load_test(base_url: str, total_events: int):
    print(f"\n{'═'*60}")
    print(f"  LinkPlease Load Test  —  {total_events} events → {base_url}")
    print(f"{'═'*60}\n")

    # 1. Health check
    async with httpx.AsyncClient() as client:
        try:
            h = await client.get(f"{base_url}/health", timeout=5.0)
            print(f"  Health: {h.json()}")
        except Exception as e:
            print(f"  ❌ Backend not reachable: {e}")
            return

    # 2. Create rule
    print(f"\n  [1/4] Creating keyword rule '{KEYWORD}'...")
    await ensure_rule(base_url)

    # 3. Build payload list
    print(f"  [2/4] Generating {total_events} events ({int(DUPLICATE_RATE*100)}% dup event_ids, {int(DUPLICATE_USER_RATE*100)}% dup users)...")
    unique_users: list[str] = [rand_id("usr") for _ in range(max(1, int(total_events * (1 - DUPLICATE_USER_RATE))))]
    unique_event_ids: list[str] = []
    payloads: list[dict] = []

    for i in range(total_events):
        # Decide if duplicate event
        if unique_event_ids and random.random() < DUPLICATE_RATE:
            event_id = random.choice(unique_event_ids)
        else:
            event_id = rand_id("evt")
            unique_event_ids.append(event_id)

        # Decide if duplicate user
        if len(unique_users) > 1 and random.random() < DUPLICATE_USER_RATE:
            user_id = random.choice(unique_users)
        else:
            user_id = rand_id("usr")
            if user_id not in unique_users:
                unique_users.append(user_id)

        comment_id = rand_id("cmt")
        username = f"user_{user_id[-4:]}"
        text = f"{KEYWORD} please — comment #{i}"
        payloads.append(make_event(event_id, user_id, username, comment_id, text))

    dup_events = total_events - len(set(p["event_id"] for p in payloads))
    print(f"    → {len(set(p['event_id'] for p in payloads))} unique event_ids, ~{dup_events} duplicates")
    print(f"    → {len(set(p['data']['from']['user_id'] for p in payloads))} unique users")

    # 4. Fire all events
    print(f"\n  [3/4] Firing {total_events} events with concurrency={CONCURRENCY}...")
    results: list[dict] = []
    sem = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient() as client:
        start_all = time.perf_counter()
        tasks = [send_event(client, base_url, p, results, sem) for p in payloads]
        await asyncio.gather(*tasks)
        wall_time = time.perf_counter() - start_all

    # 5. Summarise
    print(f"\n  [4/4] Results:")
    statuses: dict[int, int] = {}
    for r in results:
        s = r["status"]
        statuses[s] = statuses.get(s, 0) + 1

    ok = statuses.get(200, 0)
    errors = {k: v for k, v in statuses.items() if k != 200}
    elapsed_times = [r["elapsed"] for r in results]
    avg_ms = (sum(elapsed_times) / len(elapsed_times)) * 1000 if elapsed_times else 0
    max_ms = max(elapsed_times) * 1000 if elapsed_times else 0
    slow = sum(1 for r in results if r["elapsed"] > 5.0)

    print(f"    Wall time          : {wall_time:.2f}s")
    print(f"    Events per second  : {total_events / wall_time:.1f}")
    print(f"    200 OK             : {ok}/{total_events}")
    print(f"    Errors             : {errors if errors else 'none'}")
    print(f"    Avg response time  : {avg_ms:.1f}ms")
    print(f"    Max response time  : {max_ms:.1f}ms")
    print(f"    Slow (>5s)         : {slow}")

    # 6. Wait briefly then check stats
    print(f"\n  Waiting 3s for worker to begin processing...")
    await asyncio.sleep(3)
    async with httpx.AsyncClient() as client:
        stats = await client.get(f"{base_url}/stats", timeout=5.0)
        print(f"\n  /stats right after load test:")
        print(f"    {json.dumps(stats.json(), indent=4)}")

    print(f"\n{'═'*60}")
    if ok == total_events:
        print("  ✅ PASS — all events returned 200 within timeout")
    else:
        print(f"  ⚠️  WARN — {total_events - ok} events did not return 200")
    if slow > 0:
        print(f"  ⚠️  WARN — {slow} events took >5 seconds (webhook must return <5s)")
    print(f"{'═'*60}\n")

# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LinkPlease load test")
    parser.add_argument("--url", default=DEFAULT_URL, help="Backend base URL")
    parser.add_argument("--events", type=int, default=TOTAL_EVENTS, help="Number of events to send")
    args = parser.parse_args()

    asyncio.run(run_load_test(args.url, args.events))
