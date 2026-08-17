import asyncio
import datetime
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import RateLimitLog, utcnow
from app.config import settings

class DMRateLimiter:
    """
    Database-backed sliding window rate limiter.
    Ensures <= 10 outgoing requests per rolling 60 seconds across all processes/workers.
    """

    def __init__(self, limit: int = 10, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._lock = asyncio.Lock()

    async def acquire_slot(self, session: AsyncSession) -> float:
        """
        Attempts to acquire a rate limit slot.
        If slot is available, records timestamp in DB and returns 0.0.
        If limit is reached, returns the wait time in seconds required before trying again.
        """
        async with self._lock:
            now = utcnow()
            cutoff = now - datetime.timedelta(seconds=self.window_seconds)

            # Purge stale logs
            await session.execute(
                delete(RateLimitLog).where(RateLimitLog.timestamp < cutoff)
            )

            # Count active requests in window
            result = await session.execute(
                select(func.count(RateLimitLog.id)).where(RateLimitLog.timestamp >= cutoff)
            )
            count = result.scalar() or 0

            if count < self.limit:
                # Slot available: log execution and return 0
                log_entry = RateLimitLog(timestamp=now)
                session.add(log_entry)
                await session.commit()
                return 0.0
            else:
                # Window full: get earliest timestamp in current window
                result_oldest = await session.execute(
                    select(func.min(RateLimitLog.timestamp)).where(RateLimitLog.timestamp >= cutoff)
                )
                oldest_ts = result_oldest.scalar()
                if oldest_ts:
                    # Calculate required sleep duration
                    if oldest_ts.tzinfo is None:
                        oldest_ts = oldest_ts.replace(tzinfo=datetime.timezone.utc)
                    elapsed = (now - oldest_ts).total_seconds()
                    wait_time = max(0.1, self.window_seconds - elapsed + 0.1)
                else:
                    wait_time = 1.0
                
                await session.commit()
                return wait_time

rate_limiter = DMRateLimiter(
    limit=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS
)

