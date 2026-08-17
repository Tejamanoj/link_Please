import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from app.database import Base

def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)

class Rule(Base):
    __tablename__ = "rules"

    id = Column(String(64), primary_key=True)
    keyword = Column(String(255), nullable=False, index=True)
    dm_message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    # Whether this rule is active and should be matched against new comments
    active = Column(Boolean, default=True, nullable=False, index=True)

    dm_jobs = relationship("DMJob", back_populates="rule", cascade="all, delete-orphan")



class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(128), unique=True, index=True, nullable=False)
    event_type = Column(String(64), nullable=False, index=True)
    comment_id = Column(String(128), nullable=False, index=True)
    post_id = Column(String(128), nullable=True)
    user_id = Column(String(128), nullable=True, index=True)
    username = Column(String(128), nullable=True)
    text = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), default="received", nullable=False)


class DMJob(Base):
    __tablename__ = "dm_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(64), ForeignKey("rules.id"), nullable=False, index=True)
    user_id = Column(String(128), nullable=False, index=True)
    comment_id = Column(String(128), nullable=False, index=True)
    message = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="queued", index=True)
    attempts = Column(Integer, default=0, nullable=False)
    dm_id = Column(String(128), nullable=True, index=True)
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    rule = relationship("Rule", back_populates="dm_jobs")

    __table_args__ = (
        UniqueConstraint("rule_id", "user_id", name="uq_rule_user"),
    )


class DuplicateBlock(Base):
    __tablename__ = "duplicate_blocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(128), nullable=False, index=True)
    comment_id = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class RateLimitLog(Base):
    __tablename__ = "rate_limit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
