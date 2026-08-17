import pytest
from app.rate_limiter import DMRateLimiter

@pytest.mark.asyncio
async def test_rate_limiter_strict_10_per_60s(db_session):
    limiter = DMRateLimiter(limit=10, window_seconds=60)

    # First 10 slots must be granted immediately (wait_time == 0.0)
    for i in range(10):
        wait_time = await limiter.acquire_slot(db_session)
        assert wait_time == 0.0, f"Slot {i+1} should have been acquired without delay"

    # The 11th request must be throttled (wait_time > 0.0)
    wait_time = await limiter.acquire_slot(db_session)
    assert wait_time > 0.0, "11th request must return positive wait duration"
