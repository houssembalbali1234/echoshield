import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models import DeviceStatus


class DeviceRegister(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    public_key: str = Field(min_length=50, max_length=1000)


class DeviceOut(BaseModel):
    id: uuid.UUID
    name: str
    status: DeviceStatus
    activates_at: datetime
    created_at: datetime
    revoked_at: datetime | None
    can_confirm: bool