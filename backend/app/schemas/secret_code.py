from datetime import datetime

from pydantic import BaseModel, Field


class SecretCodeSet(BaseModel):
    code: str = Field(min_length=6, max_length=64)


class SecretCodeStatus(BaseModel):
    has_code: bool
    pending_change: bool
    pending_active_from: datetime | None


class SecretCodeCheck(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class SecretCodeCheckResult(BaseModel):
    valid: bool
    attempts_left: int