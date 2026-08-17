import os
import hmac
import hashlib
import json
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

# Set test environment before importing app modules
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_temp.db"
os.environ["PSEUDOGRAM_API_KEY"] = "test_secret_key_123"
os.environ["WEBHOOK_SECRET"] = "test_secret_key_123"
os.environ["VERIFY_WEBHOOK_SIGNATURE"] = "true"
os.environ["MAX_DM_RETRIES"] = "3"
os.environ["WORKER_POLL_INTERVAL"] = "0.05"

from app.database import Base, get_db
import app.database as app_db
from app.main import app
from app.client import pseudogram_client

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    async with app_db.async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    yield app_db.async_engine

    async with app_db.async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    async with app_db.AsyncSessionLocal() as session:
        yield session

@pytest_asyncio.fixture(scope="function")
async def client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        async with app_db.AsyncSessionLocal() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest_asyncio.fixture(scope="function", autouse=True)
async def mock_pseudogram_client():
    from unittest.mock import patch, AsyncMock

    mock_send = AsyncMock(return_value=(200, {"dm_id": "dm_default", "status": "delivered"}, {}))
    mock_status = AsyncMock(return_value=(200, {"dm_id": "dm_default", "status": "delivered"}))

    with patch.object(pseudogram_client, "send_dm", new=mock_send), \
         patch.object(pseudogram_client, "get_dm_status", new=mock_status):
        yield

def generate_signature(payload: dict, secret: str = "test_secret_key_123") -> str:
    raw_bytes = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"

def generate_raw_signature(raw_bytes: bytes, secret: str = "test_secret_key_123") -> str:
    sig = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    return f"sha256={sig}"


