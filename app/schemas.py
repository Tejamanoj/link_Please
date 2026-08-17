import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict

# --- Rule Schemas ---
class RuleCreate(BaseModel):
    keyword: str = Field(..., description="Keyword to match in comments")
    dm_message: str = Field(..., description="DM message to send")

    @field_validator("keyword")
    @classmethod
    def keyword_must_not_be_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Keyword cannot be empty or whitespace only")
        return s

    @field_validator("dm_message")
    @classmethod
    def dm_message_must_not_be_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("DM message cannot be empty or whitespace only")
        return s

class RuleResponse(BaseModel):
    rule_id: str
    keyword: str
    dm_message: str
    active: bool = True
    created_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- Webhook Schemas ---
class WebhookUserData(BaseModel):
    user_id: Optional[str] = None
    username: Optional[str] = None

class WebhookEventData(BaseModel):
    comment_id: str
    post_id: Optional[str] = None
    text: Optional[str] = None
    created_at: Optional[datetime.datetime] = None
    from_user: Optional[WebhookUserData] = Field(default=None, alias="from")

    model_config = ConfigDict(populate_by_name=True)

class WebhookPayload(BaseModel):
    event_id: str
    event_type: str
    sent_at: Optional[datetime.datetime] = None
    data: WebhookEventData

class WebhookResponse(BaseModel):
    status: str = "ok"
    event_id: str
    message: Optional[str] = None

# --- Stats Schema ---
class StatsResponse(BaseModel):
    sent: int
    failed: int
    queued: int
    duplicates_blocked: int

# --- Frontend API Schemas ---
class DMJobResponse(BaseModel):
    """DM job record for the admin dashboard table."""
    id: int
    rule_id: str
    rule_keyword: Optional[str] = None  # joined from rule
    user_id: str
    comment_id: str
    status: str
    attempts: int
    dm_id: Optional[str] = None
    last_error: Optional[str] = None
    next_retry_at: Optional[datetime.datetime] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)

class WebhookEventResponse(BaseModel):
    """Webhook event record for the admin dashboard table."""
    id: int
    event_id: str
    event_type: str
    comment_id: str
    user_id: Optional[str] = None
    username: Optional[str] = None
    text: Optional[str] = None
    status: str
    created_at: datetime.datetime
    processed_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)

# --- PseudoGram API Schemas ---
class DMSendRequest(BaseModel):
    recipient_user_id: str
    message: str
    comment_id: str

class DMSendResponse(BaseModel):
    dm_id: Optional[str] = None
    status: str
    error: Optional[str] = None

class DMStatusResponse(BaseModel):
    dm_id: str
    status: str  # e.g., 'queued', 'delivered', 'failed'
    error: Optional[str] = None

