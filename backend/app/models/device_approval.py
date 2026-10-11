import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DeviceApproval(TimestampMixin, Base):
    __tablename__ = "device_approvals"
    # Une personne ne peut valider le même appareil qu'une seule fois.
    __table_args__ = (UniqueConstraint("device_id", "approver_id", name="uq_device_approver"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # L'appareil à valider (le nouveau téléphone de Papa).
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    # La personne qui valide (Demo, Maman...).
    approver_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # L'appareil avec lequel elle a signé sa validation, pour l'audit.
    approver_device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )