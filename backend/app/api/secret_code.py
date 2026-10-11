import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.redis import redis_client
from app.core.security import hash_password, verify_password
from app.db.session import get_db
from app.models import Circle, CircleMember, CircleRole, User
from app.schemas.secret_code import (
    SecretCodeCheck,
    SecretCodeCheckResult,
    SecretCodeSet,
    SecretCodeStatus,
)
from app.services.risk import normalize

router = APIRouter(prefix="/circles/{circle_id}/secret-code", tags=["secret code"])

CHANGE_DELAY_HOURS = 24
MAX_FAILED_ATTEMPTS = 3
LOCKOUT_SECONDS = 15 * 60
MIN_CODE_LENGTH = 6
MANAGER_ROLES = (CircleRole.OWNER, CircleRole.ADMIN)


def _fails_key(circle_id: uuid.UUID) -> str:
    return f"secret_code_fails:{circle_id}"


async def _get_circle_for_member(
    db: AsyncSession, circle_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[Circle, CircleMember]:
    membership = await db.scalar(
        select(CircleMember).where(
            CircleMember.circle_id == circle_id,
            CircleMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cercle introuvable")
    circle = await db.get(Circle, circle_id)
    return circle, membership


def _promote_pending_code(circle: Circle, now: datetime) -> bool:
    """Active le nouveau code si son délai de sécurité est écoulé."""
    if (
        circle.next_secret_code_hash
        and circle.next_secret_code_from
        and circle.next_secret_code_from <= now
    ):
        circle.secret_code_hash = circle.next_secret_code_hash
        circle.next_secret_code_hash = None
        circle.next_secret_code_from = None
        return True
    return False


def _status(circle: Circle) -> SecretCodeStatus:
    return SecretCodeStatus(
        has_code=circle.secret_code_hash is not None,
        pending_change=circle.next_secret_code_hash is not None,
        pending_active_from=circle.next_secret_code_from,
    )


@router.put("", response_model=SecretCodeStatus)
async def set_secret_code(
    circle_id: uuid.UUID,
    data: SecretCodeSet,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecretCodeStatus:
    circle, membership = await _get_circle_for_member(db, circle_id, current_user.id)
    if membership.role not in MANAGER_ROLES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Seuls le propriétaire et les administrateurs peuvent changer le code",
        )

    normalized = normalize(data.code)
    if len(normalized) < MIN_CODE_LENGTH:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Le code doit contenir au moins {MIN_CODE_LENGTH} caractères",
        )

    now = datetime.now(timezone.utc)
    _promote_pending_code(circle, now)
    new_hash = hash_password(normalized)

    if circle.secret_code_hash is None:
        # Premier code du cercle : actif immédiatement.
        circle.secret_code_hash = new_hash
    else:
        # Changement de code : l'ancien reste valable pendant le délai de sécurité.
        circle.next_secret_code_hash = new_hash
        circle.next_secret_code_from = now + timedelta(hours=CHANGE_DELAY_HOURS)

    await db.commit()
    return _status(circle)


@router.get("", response_model=SecretCodeStatus)
async def get_secret_code_status(
    circle_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecretCodeStatus:
    circle, _ = await _get_circle_for_member(db, circle_id, current_user.id)
    if _promote_pending_code(circle, datetime.now(timezone.utc)):
        await db.commit()
    return _status(circle)


@router.post("/check", response_model=SecretCodeCheckResult)
async def check_secret_code(
    circle_id: uuid.UUID,
    data: SecretCodeCheck,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SecretCodeCheckResult:
    circle, _ = await _get_circle_for_member(db, circle_id, current_user.id)

    key = _fails_key(circle_id)
    failures = int(await redis_client.get(key) or 0)
    if failures >= MAX_FAILED_ATTEMPTS:
        remaining_seconds = await redis_client.ttl(key)
        minutes = max(1, (remaining_seconds + 59) // 60)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Trop d'essais incorrects. Réessayez dans {minutes} min.",
        )

    if _promote_pending_code(circle, datetime.now(timezone.utc)):
        await db.commit()
    if circle.secret_code_hash is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Aucun code secret n'est défini pour ce cercle")

    if verify_password(normalize(data.code), circle.secret_code_hash):
        await redis_client.delete(key)
        return SecretCodeCheckResult(valid=True, attempts_left=MAX_FAILED_ATTEMPTS)

    failures = await redis_client.incr(key)
    if failures == 1:
        await redis_client.expire(key, LOCKOUT_SECONDS)
    return SecretCodeCheckResult(valid=False, attempts_left=max(0, MAX_FAILED_ATTEMPTS - failures))