import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import CircleKind, CircleRole


class CircleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    kind: CircleKind = CircleKind.FAMILY


class CircleOut(BaseModel):
    id: uuid.UUID
    name: str
    kind: CircleKind
    created_at: datetime
    my_role: CircleRole


class MemberOut(BaseModel):
    user_id: uuid.UUID
    full_name: str
    email: str
    role: CircleRole
    trusted_from: datetime
    is_trusted: bool


class CircleDetail(CircleOut):
    members: list[MemberOut]


class InvitationCreated(BaseModel):
    token: str
    expires_at: datetime


class AcceptInvitation(BaseModel):
    token: str = Field(min_length=20, max_length=200)