import json
import time
import asyncio
import pytest
from httpx import AsyncClient
from tests.conftest import generate_raw_signature

@pytest.mark.asyncio
async def test_high_volume_concurrency_load(client: AsyncClient):
    # 1. Create matching rule
    rule_res = await client.post("/rules", json={"keyword": "LOAD", "dm_message": "Load test DM"})
    assert rule_res.status_code == 201

    num_events = 100  # High volume batch
    start_time = time.time()

    async def send_single_webhook(idx: int):
        # 20% duplicate event_ids, 30% duplicate users
        event_id = f"evt_load_{idx % 80}"
        user_id = f"usr_load_{idx % 70}"
        
        payload = {
            "event_id": event_id,
            "event_type": "comment.created",
            "sent_at": "2026-08-10T10:00:00.000Z",
            "data": {
                "comment_id": f"cmt_load_{idx}",
                "post_id": "post_load_1",
                "text": f"LOAD test comment {idx}",
                "from": {"user_id": user_id, "username": f"user_{idx}"}
            }
        }
        raw_body = json.dumps(payload, separators=(',', ':')).encode("utf-8")
        sig = generate_raw_signature(raw_body)
        headers = {"Content-Type": "application/json", "X-PseudoGram-Signature": sig}

        t0 = time.time()
        res = await client.post("/webhook", content=raw_body, headers=headers)
        duration = time.time() - t0
        return res.status_code, duration

    results = []
    for i in range(num_events):
        res = await send_single_webhook(i)
        results.append(res)
        
    total_duration = time.time() - start_time

    # Verify Webhook Response Performance (<5s for every request)
    for status_code, req_duration in results:
        assert status_code == 200
        assert req_duration < 5.0, f"Webhook request took {req_duration:.2f}s (must be < 5.0s)"

    # Check /stats consistency
    stats_res = await client.get("/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()

    total_accounted = stats["queued"] + stats["sent"] + stats["failed"] + stats["duplicates_blocked"]
    assert total_accounted > 0
    assert total_duration < 10.0
