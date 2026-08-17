import uuid
import logging
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy import select, func, update, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Rule, WebhookEvent, DMJob, DuplicateBlock, utcnow
from app.schemas import RuleCreate, StatsResponse

logger = logging.getLogger("linkplease.services")

async def create_rule(session: AsyncSession, rule_in: RuleCreate) -> Rule:
    """Creates a new keyword rule with a unique rule_id."""
    rule_id = f"rule_{uuid.uuid4().hex[:12]}"
    rule = Rule(
        id=rule_id,
        keyword=rule_in.keyword.strip(),
        dm_message=rule_in.dm_message.strip()
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    logger.info(f"Rule created: id={rule.id}, keyword='{rule.keyword}'")
    return rule

async def get_all_rules(session: AsyncSession) -> List[Rule]:
    """Retrieves only ACTIVE rules (used for keyword matching)."""
    result = await session.execute(select(Rule).where(Rule.active == True))
    return list(result.scalars().all())

async def get_all_rules_admin(session: AsyncSession) -> List[Rule]:
    """Retrieves ALL rules including inactive (used for admin UI)."""
    result = await session.execute(select(Rule).order_by(desc(Rule.created_at)))
    return list(result.scalars().all())

async def toggle_rule_active(session: AsyncSession, rule_id: str) -> Optional[Rule]:
    """Toggles the active state of a rule. Returns updated rule or None if not found."""
    rule = await session.get(Rule, rule_id)
    if not rule:
        return None
    rule.active = not rule.active
    await session.commit()
    await session.refresh(rule)
    logger.info(f"Rule toggled: id={rule.id}, active={rule.active}")
    return rule

async def get_recent_jobs(session: AsyncSession, limit: int = 50) -> List[DMJob]:
    """Retrieves the most recent DM jobs for the admin dashboard, with rule eagerly loaded."""
    result = await session.execute(
        select(DMJob)
        .options(selectinload(DMJob.rule))
        .order_by(desc(DMJob.updated_at))
        .limit(limit)
    )
    return list(result.scalars().all())

async def get_recent_events(session: AsyncSession, limit: int = 50) -> List[WebhookEvent]:
    """Retrieves the most recent webhook events for the admin dashboard."""
    result = await session.execute(
        select(WebhookEvent).order_by(desc(WebhookEvent.created_at)).limit(limit)
    )
    return list(result.scalars().all())

async def ingest_webhook_payload(
    session: AsyncSession,
    payload: Dict[str, Any]
) -> Tuple[bool, str, Optional[WebhookEvent]]:
    """
    Ingests and processes webhook payload atomically.
    Returns (success, status_code_or_reason, WebhookEvent).
    """
    event_id = payload.get("event_id")
    event_type = payload.get("event_type", "unknown")
    sent_at_raw = payload.get("sent_at")
    data = payload.get("data") or {}

    if not event_id:
        return False, "missing_event_id", None

    comment_id = data.get("comment_id", "")
    post_id = data.get("post_id")
    text = data.get("text", "")
    from_user = data.get("from") or {}
    user_id = from_user.get("user_id") if isinstance(from_user, dict) else None
    username = from_user.get("username") if isinstance(from_user, dict) else None

    # Step 1: Duplicate event check
    existing_evt = await session.execute(
        select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    )
    if existing_evt.scalar_one_or_none() is not None:
        logger.warning(f"Duplicate webhook event detected: event_id={event_id}")
        return True, "duplicate_event", None

    event = WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        comment_id=comment_id,
        post_id=post_id,
        user_id=user_id,
        username=username,
        text=text,
        status="received"
    )
    session.add(event)

    # Step 2: Handle event types
    if event_type == "comment.created":
        if text and user_id:
            # Check if comment was already deleted out-of-order
            deletion_evt = await session.execute(
                select(WebhookEvent).where(
                    WebhookEvent.comment_id == comment_id,
                    WebhookEvent.event_type == "comment.deleted"
                )
            )
            if deletion_evt.scalar_one_or_none() is not None:
                logger.info(f"Comment {comment_id} was already marked deleted (out-of-order). Skipping DM creation.")
            else:
                rules = await get_all_rules(session)
                comment_text_lower = text.lower()

                for rule in rules:
                    if rule.keyword.lower() in comment_text_lower:
                        logger.info(f"Rule matched: rule_id={rule.id}, comment_id={comment_id}, user_id={user_id}")
                        
                        # Idempotency check: (rule_id, user_id)
                        existing_job = await session.execute(
                            select(DMJob).where(DMJob.rule_id == rule.id, DMJob.user_id == user_id)
                        )
                        if existing_job.scalar_one_or_none() is not None:
                            logger.info(f"Duplicate DM attempt blocked: rule_id={rule.id}, user_id={user_id}")
                            block_record = DuplicateBlock(
                                rule_id=rule.id,
                                user_id=user_id,
                                comment_id=comment_id
                            )
                            session.add(block_record)
                        else:
                            try:
                                async with session.begin_nested():
                                    dm_job = DMJob(
                                        rule_id=rule.id,
                                        user_id=user_id,
                                        comment_id=comment_id,
                                        message=rule.dm_message,
                                        status="queued"
                                    )
                                    session.add(dm_job)
                                    await session.flush()
                                    logger.info(f"DM Job queued: user_id={user_id}")
                            except IntegrityError:
                                logger.info(f"Concurrent race: Duplicate DM attempt blocked: rule_id={rule.id}, user_id={user_id}")
                                block_record = DuplicateBlock(
                                    rule_id=rule.id,
                                    user_id=user_id,
                                    comment_id=comment_id
                                )
                                session.add(block_record)

    elif event_type == "comment.deleted":
        if comment_id:
            logger.info(f"Handling comment.deleted for comment_id={comment_id}")
            await session.execute(
                update(DMJob)
                .where(DMJob.comment_id == comment_id)
                .where(DMJob.status.in_(["queued", "sending", "waiting_retry"]))
                .values(status="blocked", last_error="comment_deleted", updated_at=utcnow())
            )

    event.status = "processed"
    event.processed_at = utcnow()

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.warning(f"IntegrityError caught during commit for event_id={event_id}")
        return True, "duplicate_event", None

    return True, "processed", event

async def get_stats(session: AsyncSession) -> StatsResponse:
    """
    Computes system statistics directly from persistent database state.
    """
    res_sent = await session.execute(
        select(func.count(DMJob.id)).where(DMJob.status == "delivered")
    )
    sent_count = res_sent.scalar() or 0

    res_failed = await session.execute(
        select(func.count(DMJob.id)).where(DMJob.status == "failed")
    )
    failed_count = res_failed.scalar() or 0

    res_queued = await session.execute(
        select(func.count(DMJob.id)).where(
            DMJob.status.in_(["queued", "sending", "waiting_retry", "waiting_reconciliation"])
        )
    )
    queued_count = res_queued.scalar() or 0

    res_dup = await session.execute(
        select(func.count(DuplicateBlock.id))
    )
    dup_count = res_dup.scalar() or 0

    return StatsResponse(
        sent=sent_count,
        failed=failed_count,
        queued=queued_count,
        duplicates_blocked=dup_count
    )
