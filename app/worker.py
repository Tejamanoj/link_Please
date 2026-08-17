import asyncio
import logging
import datetime
from typing import Optional
from sqlalchemy import select, update

import app.database as db
from app.models import DMJob, utcnow
from app.client import pseudogram_client
from app.rate_limiter import rate_limiter
from app.config import settings

logger = logging.getLogger("linkplease.worker")

class BackgroundWorker:
    """
    Background worker for processing queued DM jobs, retries, rate limiting, and DM reconciliation.
    """

    def __init__(self):
        self._running = True
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Starts background worker task."""
        if not self._running:
            self._running = True
            # Recover stuck jobs on startup
            await self.recover_stuck_jobs()
            self._task = asyncio.create_task(self._run_loop())
            logger.info("Background worker started.")

    async def stop(self):
        """Stops background worker task gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info("Background worker stopped.")

    async def recover_stuck_jobs(self):
        """Resets jobs stuck in 'sending' status back to 'queued' on startup."""
        async with db.AsyncSessionLocal() as session:
            await session.execute(
                update(DMJob)
                .where(DMJob.status == "sending")
                .values(status="queued", updated_at=utcnow())
            )
            await session.commit()
            logger.info("Stuck jobs recovered.")

    async def _run_loop(self):
        """Main periodic polling loop."""
        while self._running:
            try:
                await self.process_jobs_batch()
                await self.reconcile_pending_dms()
            except Exception as exc:
                logger.error(f"Error in worker loop: {exc}", exc_info=True)
            
            await asyncio.sleep(settings.WORKER_POLL_INTERVAL)

    async def process_jobs_batch(self):
        """Processes pending queued or retryable jobs."""
        async with db.AsyncSessionLocal() as session:
            now = utcnow()
            # Fetch jobs ready for processing
            stmt = (
                select(DMJob)
                .where(DMJob.status.in_(["queued", "waiting_retry"]))
                .where(
                    (DMJob.next_retry_at == None) | (DMJob.next_retry_at <= now)
                )
                .limit(10)
            )
            result = await session.execute(stmt)
            jobs = list(result.scalars().all())

            for job in jobs:
                if not self._running:
                    break

                # Atomic status transition to 'sending' to avoid race conditions
                job.status = "sending"
                job.updated_at = utcnow()
                await session.commit()

                # Process individual job
                await self._process_single_job(job.id)

    async def _process_single_job(self, job_id: int):
        """Processes a single claimed DM job."""
        async with db.AsyncSessionLocal() as session:
            job = await session.get(DMJob, job_id)
            if not job or job.status != "sending":
                return

            # Acquire rate limit slot
            wait_seconds = await rate_limiter.acquire_slot(session)
            if wait_seconds > 0:
                logger.info(f"Rate limit reached. Re-queueing job {job.id} after {wait_seconds:.2f}s")
                job.status = "waiting_retry"
                job.next_retry_at = utcnow() + datetime.timedelta(seconds=wait_seconds)
                job.last_error = "Rate limit throttle applied"
                await session.commit()
                return

            # Execute API Call
            job.attempts += 1
            logger.info(f"Attempting DM send for job_id={job.id}, recipient={job.user_id}, attempt={job.attempts}")
            
            status_code, data, headers = await pseudogram_client.send_dm(
                job_id=job.id,
                recipient_user_id=job.user_id,
                message=job.message,
                comment_id=job.comment_id
            )

            if status_code in (200, 202):
                dm_id = data.get("dm_id")
                dm_status = data.get("status", "queued")
                job.dm_id = dm_id

                if dm_status == "delivered":
                    job.status = "delivered"
                    job.last_error = None
                    logger.info(f"Job {job.id} DM delivered immediately: dm_id={dm_id}")
                else:
                    job.status = "waiting_reconciliation"
                    job.last_error = None
                    logger.info(f"Job {job.id} DM queued by API: dm_id={dm_id}")

            elif status_code == 429:
                # Rate limited by mock API
                retry_after_hdr = headers.get("Retry-After") or headers.get("retry-after")
                try:
                    retry_after = int(retry_after_hdr) if retry_after_hdr else 5
                except ValueError:
                    retry_after = 5

                job.status = "waiting_retry"
                job.next_retry_at = utcnow() + datetime.timedelta(seconds=retry_after)
                job.last_error = f"API 429 Rate limited (Retry-After: {retry_after}s)"
                logger.warning(f"Job {job.id} rate limited by mock API. Retrying in {retry_after}s")

            elif status_code == 500:
                # Retryable internal error
                delay = 2 ** (job.attempts - 1)
                if job.attempts >= settings.MAX_DM_RETRIES:
                    job.status = "failed"
                    job.last_error = f"HTTP 500 max retries ({settings.MAX_DM_RETRIES}) reached: {data}"
                    logger.error(f"Job {job.id} permanently failed after {job.attempts} attempts.")
                else:
                    job.status = "waiting_retry"
                    job.next_retry_at = utcnow() + datetime.timedelta(seconds=delay)
                    job.last_error = f"HTTP 500 retryable error: {data}"
                    logger.warning(f"Job {job.id} failed with 500. Retrying in {delay}s")

            else:
                # 400 or other non-retryable error
                job.status = "failed"
                job.last_error = f"HTTP {status_code}: {data}"
                logger.error(f"Job {job.id} failed with permanent error HTTP {status_code}: {data}")

            job.updated_at = utcnow()
            await session.commit()

    async def reconcile_pending_dms(self):
        """Polls status of DMs waiting for reconciliation."""
        async with db.AsyncSessionLocal() as session:
            stmt = (
                select(DMJob)
                .where(DMJob.status == "waiting_reconciliation")
                .where(DMJob.dm_id != None)
                .limit(10)
            )
            result = await session.execute(stmt)
            jobs = list(result.scalars().all())

            for job in jobs:
                if not self._running:
                    break

                status_code, data = await pseudogram_client.get_dm_status(job.dm_id)
                if status_code == 200:
                    dm_status = data.get("status")
                    if dm_status == "delivered":
                        job.status = "delivered"
                        job.last_error = None
                        job.updated_at = utcnow()
                        logger.info(f"Job {job.id} reconciled as DELIVERED.")
                    elif dm_status == "failed":
                        if job.attempts < settings.MAX_DM_RETRIES:
                            job.status = "waiting_retry"
                            job.next_retry_at = utcnow() + datetime.timedelta(seconds=2)
                            job.last_error = "Reconciliation reported failure; re-queueing"
                        else:
                            job.status = "failed"
                            job.last_error = "Reconciliation reported failure; max attempts reached"
                        job.updated_at = utcnow()
                        logger.warning(f"Job {job.id} reconciled as FAILED.")
                
            await session.commit()

worker = BackgroundWorker()
