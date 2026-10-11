import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import VerificationStatus
from app.schemas.risk import RiskReportOut


class VerificationCreate(BaseModel):
    circle_id: uuid.UUID
    claimed_user_id: uuid.UUID
    note: str | None = Field(default=None, max_length=500)


class VerificationOut(BaseModel):
    id: uuid.UUID
    circle_id: uuid.UUID
    requester_id: uuid.UUID
    claimed_user_id: uuid.UUID
    note: str | None
    status: VerificationStatus
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None
    risk: RiskReportOut


class IncomingChallenge(BaseModel):
    id: uuid.UUID
    requester_name: str
    note: str | None
    expires_at: datetime
    message_to_sign_confirm: str
    message_to_sign_deny: str


class VerificationAnswer(BaseModel):
    device_id: uuid.UUID
    decision: Literal["confirm", "deny"]
    signature: str = Field(min_length=20, max_length=500)