import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy import select
from app.client import pseudogram_client
from app.worker import BackgroundWorker
from app.models import DMJob
from app.services import create_rule, ingest_webhook_payload
from app.schemas import RuleCreate

def select_job_by_user(user_id: str):
    return select(DMJob).where(DMJob.user_id == user_id)

@pytest.mark.asyncio
async def test_worker_202_accepted_and_reconciliation(db_session):
    # Setup rule and DM job
    rule = await create_rule(db_session, RuleCreate(keyword="DISCOUNT", dm_message="Discount code"))
    payload = {
        "event_id": "evt_ext_202",
        "event_type": "comment.created",
        "data": {"comment_id": "cmt_202", "text": "DISCOUNT", "from": {"user_id": "usr_202"}}
    }
    await ingest_webhook_payload(db_session, payload)

    worker = BackgroundWorker()

    # Mock send_dm response: 202 queued
    with patch.object(
        pseudogram_client,
        "send_dm",
        new_callable=AsyncMock,
        return_value=(202, {"dm_id": "dm_mock_202", "status": "queued"}, {})
    ):
        await worker.process_jobs_batch()

    # Fetch fresh job state from DB
    res = await db_session.execute(select_job_by_user("usr_202"))
    job = res.scalar_one()
    await db_session.refresh(job)

    assert job.status == "waiting_reconciliation"
    assert job.dm_id == "dm_mock_202"

    # Mock get_dm_status: 200 delivered
    with patch.object(
        pseudogram_client,
        "get_dm_status",
        new_callable=AsyncMock,
        return_value=(200, {"dm_id": "dm_mock_202", "status": "delivered"})
    ):
        await worker.reconcile_pending_dms()

    # Verify job status updated to delivered
    await db_session.refresh(job)
    assert job.status == "delivered"

@pytest.mark.asyncio
async def test_worker_500_exponential_backoff_and_failure(db_session):
    rule = await create_rule(db_session, RuleCreate(keyword="FAIL", dm_message="Fail test"))
    payload = {
        "event_id": "evt_ext_500",
        "event_type": "comment.created",
        "data": {"comment_id": "cmt_500", "text": "FAIL", "from": {"user_id": "usr_500"}}
    }
    await ingest_webhook_payload(db_session, payload)

    worker = BackgroundWorker()

    # Mock 500 error 3 times
    with patch.object(
        pseudogram_client,
        "send_dm",
        new_callable=AsyncMock,
        return_value=(500, {"error": "internal_error"}, {})
    ):
        # Attempt 1
        await worker.process_jobs_batch()
        job = (await db_session.execute(select_job_by_user("usr_500"))).scalar_one()
        await db_session.refresh(job)
        assert job.attempts == 1
        assert job.status == "waiting_retry"

        # Force next_retry_at to None to simulate immediate retry in test
        job.next_retry_at = None
        await db_session.commit()

        # Attempt 2
        await worker.process_jobs_batch()
        await db_session.refresh(job)
        assert job.attempts == 2
        assert job.status == "waiting_retry"

        job.next_retry_at = None
        await db_session.commit()

        # Attempt 3 (Max retries = 3)
        await worker.process_jobs_batch()
        await db_session.refresh(job)
        assert job.attempts == 3
        assert job.status == "failed"

@pytest.mark.asyncio
async def test_worker_429_rate_limited(db_session):
    rule = await create_rule(db_session, RuleCreate(keyword="LIMIT", dm_message="Limit test"))
    payload = {
        "event_id": "evt_ext_429",
        "event_type": "comment.created",
        "data": {"comment_id": "cmt_429", "text": "LIMIT", "from": {"user_id": "usr_429"}}
    }
    await ingest_webhook_payload(db_session, payload)

    worker = BackgroundWorker()

    with patch.object(
        pseudogram_client,
        "send_dm",
        new_callable=AsyncMock,
        return_value=(429, {"error": "rate_limited"}, {"Retry-After": "10"})
    ):
        await worker.process_jobs_batch()

    job = (await db_session.execute(select_job_by_user("usr_429"))).scalar_one()
    await db_session.refresh(job)
    assert job.status == "waiting_retry"
    assert job.next_retry_at is not None
