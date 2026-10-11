import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.clock import immediately
from app.api.deps import get_current_user
from app.core.crypto import InvalidPublicKey, normalize_public_key, verify_signature
from app.db.session import get_db
from app.models import CircleMember, Device, DeviceApproval, DeviceStatus, User
from app.schemas.device import (
    DeviceApprovalRequest,
    DeviceApprovalStatus,
    DeviceOut,
    DeviceRegister,
)

router = APIRouter(prefix="/devices", tags=["devices"])

NEW_DEVICE_DELAY_HOURS = 24
MAX_ACTIVE_DEVICES = 5
REQUIRED_APPROVALS = 2


def approval_message(device_id: uuid.UUID, approver_id: uuid.UUID) -> str:
    # Lie la signature à CET appareil et à CETTE personne qui valide.
    return f"echoshield:v1:approve-device:{device_id}:{approver_id}"


def _device_out(device: Device, now: datetime) -> DeviceOut:
    return DeviceOut(
        id=device.id,
        name=device.name,
        status=device.status,
        activates_at=device.activates_at,
        created_at=device.created_at,
        revoked_at=device.revoked_at,
        can_confirm=device.can_confirm(now),
    )


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def register_device(
    data: DeviceRegister,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceOut:
    try:
        public_key = normalize_public_key(data.public_key)
    except InvalidPublicKey as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    if await db.scalar(select(Device.id).where(Device.public_key == public_key)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette clé est déjà enregistrée")

    active_count = await db.scalar(
        select(func.count())
        .select_from(Device)
        .where(Device.user_id == current_user.id, Device.status == DeviceStatus.ACTIVE)
    )
    if active_count >= MAX_ACTIVE_DEVICES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Maximum {MAX_ACTIVE_DEVICES} appareils actifs. Révoquez-en un d'abord.",
        )

    # Le tout premier appareil d'un compte est actif tout de suite.
    # Les suivants attendent 24 h, y compris après la révocation de tous les autres :
    # un attaquant qui prend le compte ne peut pas ajouter son téléphone et confirmer aussitôt.
    total_count = await db.scalar(
        select(func.count()).select_from(Device).where(Device.user_id == current_user.id)
    )
    now = datetime.now(timezone.utc)
    activates_at = immediately() if total_count == 0 else now + timedelta(hours=NEW_DEVICE_DELAY_HOURS)

    device = Device(
        user_id=current_user.id,
        name=data.name.strip(),
        public_key=public_key,
        status=DeviceStatus.ACTIVE,
        activates_at=activates_at,
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return _device_out(device, now)


@router.get("", response_model=list[DeviceOut])
async def list_devices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DeviceOut]:
    result = await db.scalars(
        select(Device).where(Device.user_id == current_user.id).order_by(Device.created_at)
    )
    now = datetime.now(timezone.utc)
    return [_device_out(device, now) for device in result.all()]


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_device(
    device_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    device = await db.scalar(
        select(Device).where(Device.id == device_id, Device.user_id == current_user.id)
    )
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appareil introuvable")
    if device.status == DeviceStatus.REVOKED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet appareil est déjà révoqué")

    device.status = DeviceStatus.REVOKED
    device.revoked_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/{device_id}/approvals", response_model=DeviceApprovalStatus)
async def approve_device(
    device_id: uuid.UUID,
    data: DeviceApprovalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeviceApprovalStatus:
    now = datetime.now(timezone.utc)

    # Verrouille l'appareil : deux validations simultanées sont traitées l'une après l'autre.
    device = await db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appareil introuvable")
    if device.user_id == current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez pas valider votre propre appareil")

    # Celui qui valide doit être membre DE CONFIANCE d'un cercle où se trouve aussi le propriétaire.
    owner_membership = aliased(CircleMember)
    shared_circle = await db.scalar(
        select(CircleMember.id)
        .join(
            owner_membership,
            (owner_membership.circle_id == CircleMember.circle_id)
            & (owner_membership.user_id == device.user_id),
        )
        .where(CircleMember.user_id == current_user.id, CircleMember.trusted_from <= now)
        .limit(1)
    )
    if shared_circle is None:
        # 404 : un inconnu n'apprend même pas que cet appareil existe.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Appareil introuvable")

    if device.status != DeviceStatus.ACTIVE or device.activates_at <= now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cet appareil n'a pas besoin de validation")

    approver_device = await db.scalar(
        select(Device).where(Device.id == data.approver_device_id, Device.user_id == current_user.id)
    )
    if approver_device is None or not approver_device.can_confirm(now):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Votre appareil n'est pas autorisé à valider")

    message = approval_message(device.id, current_user.id).encode()
    if not verify_signature(approver_device.public_key, message, data.signature):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Signature invalide")

    already_approved = await db.scalar(
        select(DeviceApproval.id).where(
            DeviceApproval.device_id == device.id,
            DeviceApproval.approver_id == current_user.id,
        )
    )
    if already_approved:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous avez déjà validé cet appareil")

    db.add(
        DeviceApproval(
            device_id=device.id,
            approver_id=current_user.id,
            approver_device_id=approver_device.id,
        )
    )
    await db.flush()

    approvals = await db.scalar(
        select(func.count()).select_from(DeviceApproval).where(DeviceApproval.device_id == device.id)
    )
    if approvals >= REQUIRED_APPROVALS:
        device.activates_at = immediately()

    await db.commit()
    return DeviceApprovalStatus(
        device_id=device.id,
        approvals=approvals,
        required=REQUIRED_APPROVALS,
        can_confirm=device.can_confirm(now),
    )