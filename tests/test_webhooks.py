import json
import pytest
from httpx import AsyncClient
from tests.conftest import generate_raw_signature

@pytest.mark.asyncio
async def test_webhook_valid_signature_and_payload(client: AsyncClient):
    payload = {
        "event_id": "evt_01J8ZQ4K2N7RXA",
        "event_type": "comment.created",
        "sent_at": "2026-08-10T09:14:22.481Z",
        "data": {
            "comment_id": "cmt_9f2a7c",
            "post_id": "post_44de1b",
            "text": "PRICE please",
            "created_at": "2026-08-10T09:14:21.900Z",
            "from": {
                "user_id": "usr_3b91fe",
                "username": "arjun.shoots"
            }
        }
    }
    raw_body = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    sig = generate_raw_signature(raw_body)
    
    headers = {
        "Content-Type": "application/json",
        "X-PseudoGram-Signature": sig
    }
    response = await client.post("/webhook", content=raw_body, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["event_id"] == "evt_01J8ZQ4K2N7RXA"

@pytest.mark.asyncio
async def test_webhook_invalid_signature_rejected(client: AsyncClient):
    payload = {"event_id": "evt_sig_test", "event_type": "comment.created", "data": {"comment_id": "cmt_1"}}
    raw_body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-PseudoGram-Signature": "sha256=invalid_hex_string"}
    
    response = await client.post("/webhook", content=raw_body, headers=headers)
    assert response.status_code == 401
    assert "Invalid signature" in response.json()["detail"]

@pytest.mark.asyncio
async def test_webhook_duplicate_event_id(client: AsyncClient):
    payload = {
        "event_id": "evt_dup_123",
        "event_type": "comment.created",
        "data": {"comment_id": "cmt_dup_1", "text": "price", "from": {"user_id": "usr_dup"}}
    }
    raw_body = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    sig = generate_raw_signature(raw_body)
    headers = {"Content-Type": "application/json", "X-PseudoGram-Signature": sig}

    # First delivery
    r1 = await client.post("/webhook", content=raw_body, headers=headers)
    assert r1.status_code == 200

    # Second delivery (Duplicate event)
    r2 = await client.post("/webhook", content=raw_body, headers=headers)
    assert r2.status_code == 200
    assert "duplicate_event" in r2.json()["message"]

@pytest.mark.asyncio
async def test_webhook_comment_deleted(client: AsyncClient):
    payload = {
        "event_id": "evt_del_456",
        "event_type": "comment.deleted",
        "data": {"comment_id": "cmt_deleted_123"}
    }
    raw_body = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    sig = generate_raw_signature(raw_body)
    headers = {"Content-Type": "application/json", "X-PseudoGram-Signature": sig}

    response = await client.post("/webhook", content=raw_body, headers=headers)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_webhook_out_of_order_comment_deleted(client: AsyncClient, db_session):
    # 1. Create rule
    await client.post("/rules", json={"keyword": "PRICE", "dm_message": "Price list link"})

    comment_id = "cmt_ooo_123"
    user_id = "usr_ooo_456"

    # 2. Deletion event arrives FIRST (out-of-order)
    p_del = {
        "event_id": "evt_ooo_del",
        "event_type": "comment.deleted",
        "data": {"comment_id": comment_id}
    }
    b_del = json.dumps(p_del, separators=(',', ':')).encode()
    h_del = {"Content-Type": "application/json", "X-PseudoGram-Signature": generate_raw_signature(b_del)}
    r_del = await client.post("/webhook", content=b_del, headers=h_del)
    assert r_del.status_code == 200

    # 3. Creation event arrives SECOND
    p_crt = {
        "event_id": "evt_ooo_crt",
        "event_type": "comment.created",
        "data": {"comment_id": comment_id, "text": "PRICE please", "from": {"user_id": user_id}}
    }
    b_crt = json.dumps(p_crt, separators=(',', ':')).encode()
    h_crt = {"Content-Type": "application/json", "X-PseudoGram-Signature": generate_raw_signature(b_crt)}
    r_crt = await client.post("/webhook", content=b_crt, headers=h_crt)
    assert r_crt.status_code == 200

    # 4. Verify no DM job was created for this deleted comment
    from sqlalchemy import select, func
    from app.models import DMJob
    jobs_res = await db_session.execute(
        select(func.count(DMJob.id)).where(DMJob.comment_id == comment_id)
    )
    assert jobs_res.scalar() == 0

