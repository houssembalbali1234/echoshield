import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.crypto import InvalidPublicKey, normalize_public_key
from app.db.session import get_db
from app.models import Device, DeviceStatus, User
from app.schemas.device import DeviceOut, DeviceRegister

router = APIRouter(prefix="/devices", tags=["devices"])

NEW_DEVICE_DELAY_HOURS = 24
MAX_ACTIVE_DEVICES = 5


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
    activates_at = now if total_count == 0 else now + timedelta(hours=NEW_DEVICE_DELAY_HOURS)

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