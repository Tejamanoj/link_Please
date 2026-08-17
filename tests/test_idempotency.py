import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from app.models import DMJob, DuplicateBlock, WebhookEvent
from tests.conftest import generate_raw_signature

@pytest.mark.asyncio
async def test_same_user_multiple_comments_idempotency(client: AsyncClient, db_session):
    # 1. Create rule
    rule_res = await client.post("/rules", json={"keyword": "PRICE", "dm_message": "Price list link"})
    assert rule_res.status_code == 201

    user_id = "usr_repeat_commenter"

    # Comment 1: "PRICE"
    p1 = {
        "event_id": "evt_c1",
        "event_type": "comment.created",
        "data": {"comment_id": "cmt_1", "text": "PRICE", "from": {"user_id": user_id}}
    }
    b1 = json.dumps(p1, separators=(',', ':')).encode()
    h1 = {"Content-Type": "application/json", "X-PseudoGram-Signature": generate_raw_signature(b1)}
    r1 = await client.post("/webhook", content=b1, headers=h1)
    assert r1.status_code == 200

    # Comment 2: "PRICE please"
    p2 = {
        "event_id": "evt_c2",
        "event_type": "comment.created",
        "data": {"comment_id": "cmt_2", "text": "PRICE please", "from": {"user_id": user_id}}
    }
    b2 = json.dumps(p2, separators=(',', ':')).encode()
    h2 = {"Content-Type": "application/json", "X-PseudoGram-Signature": generate_raw_signature(b2)}
    r2 = await client.post("/webhook", content=b2, headers=h2)
    assert r2.status_code == 200

    # Comment 3: "price"
    p3 = {
        "event_id": "evt_c3",
        "event_type": "comment.created",
        "data": {"comment_id": "cmt_3", "text": "price", "from": {"user_id": user_id}}
    }
    b3 = json.dumps(p3, separators=(',', ':')).encode()
    h3 = {"Content-Type": "application/json", "X-PseudoGram-Signature": generate_raw_signature(b3)}
    r3 = await client.post("/webhook", content=b3, headers=h3)
    assert r3.status_code == 200

    # Verify DB state: Exactly 1 DMJob created for (rule_id, user_id)
    jobs_res = await db_session.execute(
        select(func.count(DMJob.id)).where(DMJob.user_id == user_id)
    )
    job_count = jobs_res.scalar()
    assert job_count == 1

    # Verify duplicate blocks recorded: Exactly 2 duplicates blocked
    dups_res = await db_session.execute(
        select(func.count(DuplicateBlock.id)).where(DuplicateBlock.user_id == user_id)
    )
    dup_count = dups_res.scalar()
    assert dup_count == 2

    # Check /stats endpoint
    stats_res = await client.get("/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["duplicates_blocked"] == 2
    assert stats["queued"] == 1

@pytest.mark.asyncio
async def test_different_users_same_rule(client: AsyncClient, db_session):
    await client.post("/rules", json={"keyword": "INFO", "dm_message": "Info DM"})

    for i in range(3):
        p = {
            "event_id": f"evt_u_{i}",
            "event_type": "comment.created",
            "data": {"comment_id": f"cmt_u_{i}", "text": "INFO please", "from": {"user_id": f"usr_{i}"}}
        }
        b = json.dumps(p, separators=(',', ':')).encode()
        h = {"Content-Type": "application/json", "X-PseudoGram-Signature": generate_raw_signature(b)}
        await client.post("/webhook", content=b, headers=h)

    jobs_res = await db_session.execute(select(func.count(DMJob.id)))
    assert jobs_res.scalar() == 3

@pytest.mark.asyncio
async def test_concurrent_same_user_webhooks(client: AsyncClient, db_session):
    import asyncio
    from app.worker import worker
    await worker.stop()

    await client.post("/rules", json={"keyword": "CONCURRENCY", "dm_message": "Concurrent test DM"})

    user_id = "usr_concurrent_1"

    async def post_event(evt_id: str, cmt_id: str):
        p = {
            "event_id": evt_id,
            "event_type": "comment.created",
            "data": {"comment_id": cmt_id, "text": "CONCURRENCY test", "from": {"user_id": user_id}}
        }
        b = json.dumps(p, separators=(',', ':')).encode()
        h = {"Content-Type": "application/json", "X-PseudoGram-Signature": generate_raw_signature(b)}
        return await client.post("/webhook", content=b, headers=h)

    # Fire 5 requests concurrently for the same user
    tasks = [post_event(f"evt_conc_{i}", f"cmt_conc_{i}") for i in range(5)]
    responses = await asyncio.gather(*tasks)

    for r in responses:
        assert r.status_code == 200

    # Query committed state in a fresh DB session
    import app.database as app_db
    async with app_db.AsyncSessionLocal() as session:
        all_jobs = (await session.execute(select(DMJob))).scalars().all()
        all_dups = (await session.execute(select(DuplicateBlock))).scalars().all()

        assert len(all_jobs) == 1
        assert len(all_dups) == 4
