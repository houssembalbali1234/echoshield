import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Invitation(TimestampMixin, Base):
    __tablename__ = "invitations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    circle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("circles.id", ondelete="CASCADE"), index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_by_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))