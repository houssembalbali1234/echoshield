import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class CircleKind(str, enum.Enum):
    FAMILY = "family"
    ENTERPRISE = "enterprise"


class CircleRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class Circle(TimestampMixin, Base):
    __tablename__ = "circles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[CircleKind] = mapped_column(
        Enum(CircleKind, name="circle_kind", values_callable=lambda e: [m.value for m in e])
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    # Code secret familial : uniquement des hash Argon2, jamais le code en clair.
    secret_code_hash: Mapped[str | None] = mapped_column(String(255))
    # Nouveau code en attente : il ne devient actif qu'après le délai de sécurité.
    next_secret_code_hash: Mapped[str | None] = mapped_column(String(255))
    next_secret_code_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    members: Mapped[list["CircleMember"]] = relationship(
        back_populates="circle", cascade="all, delete-orphan"
    )


class CircleMember(TimestampMixin, Base):
    __tablename__ = "circle_members"
    __table_args__ = (UniqueConstraint("circle_id", "user_id", name="uq_circle_user"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    circle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("circles.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[CircleRole] = mapped_column(
        Enum(CircleRole, name="circle_role", values_callable=lambda e: [m.value for m in e]),
        default=CircleRole.MEMBER,
    )
    # Date à partir de laquelle ce membre peut confirmer des vérifications.
    trusted_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    circle: Mapped["Circle"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships")