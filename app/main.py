import os
import logging
from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI, Request, HTTPException, status, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db, init_db
from app.schemas import (
    RuleCreate, RuleResponse, StatsResponse, WebhookResponse, WebhookPayload,
    DMJobResponse, WebhookEventResponse
)
from app.security import verify_hmac_signature
from app.services import (
    create_rule, ingest_webhook_payload, get_stats,
    get_all_rules_admin, toggle_rule_active,
    get_recent_jobs, get_recent_events
)
from app.worker import worker

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("linkplease.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("Initializing database...")
    await init_db()

    logger.info("Starting background worker...")
    await worker.start()

    yield

    logger.info("Stopping background worker...")
    await worker.stop()
    logger.info("Shutdown complete.")

app = FastAPI(
    title="LinkPlease Instagram Automation Backend",
    description="High-reliability production backend for Instagram comment DMs.",
    version="1.0.0",
    lifespan=lifespan
)

# Allow React frontend (dev server on :5173, prod on same origin) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# Legacy HTML dashboard (kept for backward compat)
# ─────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def handle_dashboard():
    """Serves the legacy HTML dashboard (React SPA in /frontend replaces this)."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>LinkPlease Backend API Running</h1><p>Visit <a href='/docs'>/docs</a> for Swagger documentation.</p>"

# ─────────────────────────────────────────────
# Assignment Mandatory Routes
# ─────────────────────────────────────────────

@app.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED,
          summary="Create a new keyword rule",
          tags=["Rules"])
async def handle_create_rule(
    rule_in: RuleCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new keyword matching rule.
    Keyword matching is case-insensitive and matches anywhere in comment text.
    """
    try:
        rule = await create_rule(db, rule_in)
        return RuleResponse(
            rule_id=rule.id,
            keyword=rule.keyword,
            dm_message=rule.dm_message,
            active=rule.active,
            created_at=rule.created_at,
        )
    except Exception as exc:
        logger.error(f"Error creating rule: {exc}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid rule payload: {str(exc)}"
        )

@app.post("/webhook", response_model=WebhookResponse, status_code=status.HTTP_200_OK,
          summary="Receive Instagram webhook event",
          tags=["Webhook"])
async def handle_webhook(
    request: Request,
    body: Optional[WebhookPayload] = Body(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests an Instagram comment webhook event.
    Verifies HMAC-SHA256 signature, persists event uniquely, and returns HTTP 200 immediately.
    All processing (DM sending, retries) happens asynchronously in the background worker.
    """
    raw_body = await request.body()
    signature_header = request.headers.get("X-PseudoGram-Signature")

    # Step 1: Verify HMAC signature
    if not verify_hmac_signature(raw_body, signature_header):
        logger.warning("Webhook signature verification failed.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )

    # Step 2: Parse JSON payload
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    # Step 3: Ingest payload atomically (idempotent, no DM sending here)
    success, reason, event = await ingest_webhook_payload(db, payload)

    event_id = payload.get("event_id", "unknown")
    if not success and reason == "missing_event_id":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event_id"
        )

    return WebhookResponse(
        status="ok",
        event_id=event_id,
        message=f"Event ingested ({reason})"
    )

@app.get("/stats", response_model=StatsResponse, status_code=status.HTTP_200_OK,
         summary="Get system statistics",
         tags=["Stats"])
async def handle_get_stats(db: AsyncSession = Depends(get_db)):
    """
    Returns system statistics derived strictly from persistent database state.
    Stats remain correct across application restarts.
    """
    return await get_stats(db)

@app.get("/health", status_code=status.HTTP_200_OK,
         summary="Health check",
         tags=["Health"])
async def handle_health():
    """Health check endpoint for Render deployment monitoring."""
    return {"status": "ok"}

# ─────────────────────────────────────────────
# Admin / Frontend API Routes  (prefix /api)
# ─────────────────────────────────────────────

@app.get("/api/rules", response_model=List[RuleResponse], status_code=status.HTTP_200_OK,
         summary="List all rules (admin)",
         tags=["Admin API"])
async def handle_list_rules(db: AsyncSession = Depends(get_db)):
    """Returns ALL rules (active and inactive) for the admin dashboard."""
    rules = await get_all_rules_admin(db)
    return [
        RuleResponse(
            rule_id=r.id,
            keyword=r.keyword,
            dm_message=r.dm_message,
            active=r.active,
            created_at=r.created_at,
        )
        for r in rules
    ]

@app.patch("/api/rules/{rule_id}/toggle", response_model=RuleResponse,
           summary="Toggle rule active/inactive",
           tags=["Admin API"])
async def handle_toggle_rule(rule_id: str, db: AsyncSession = Depends(get_db)):
    """Activates or deactivates a rule. Inactive rules are not matched against new comments."""
    rule = await toggle_rule_active(db, rule_id)
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    return RuleResponse(
        rule_id=rule.id,
        keyword=rule.keyword,
        dm_message=rule.dm_message,
        active=rule.active,
        created_at=rule.created_at,
    )

@app.get("/api/jobs", response_model=List[DMJobResponse], status_code=status.HTTP_200_OK,
         summary="List recent DM jobs",
         tags=["Admin API"])
async def handle_list_jobs(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Returns the most recent DM jobs with their current processing status."""
    jobs = await get_recent_jobs(db, limit=limit)
    result = []
    for job in jobs:
        # Attach rule keyword for display (rule may have been deleted — handle gracefully)
        keyword = job.rule.keyword if job.rule else None
        result.append(DMJobResponse(
            id=job.id,
            rule_id=job.rule_id,
            rule_keyword=keyword,
            user_id=job.user_id,
            comment_id=job.comment_id,
            status=job.status,
            attempts=job.attempts,
            dm_id=job.dm_id,
            last_error=job.last_error,
            next_retry_at=job.next_retry_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        ))
    return result

@app.get("/api/events", response_model=List[WebhookEventResponse], status_code=status.HTTP_200_OK,
         summary="List recent webhook events",
         tags=["Admin API"])
async def handle_list_events(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """Returns the most recent webhook events received."""
    events = await get_recent_events(db, limit=limit)
    return [
        WebhookEventResponse(
            id=e.id,
            event_id=e.event_id,
            event_type=e.event_type,
            comment_id=e.comment_id,
            user_id=e.user_id,
            username=e.username,
            text=e.text,
            status=e.status,
            created_at=e.created_at,
            processed_at=e.processed_at,
        )
        for e in events
    ]
