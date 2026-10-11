import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.api.deps import get_current_user
from app.core.crypto import verify_signature
from app.core.redis import redis_client
from app.db.session import get_db
from app.schemas.risk import RiskReportOut
from app.services.risk import analyze
from app.models import CircleMember, Device, User, VerificationRequest, VerificationStatus
from app.schemas.verification import (
    IncomingChallenge,
    VerificationAnswer,
    VerificationCreate,
    VerificationOut,
)

router = APIRouter(prefix="/verifications", tags=["verifications"])

CHALLENGE_SECONDS = get_settings().challenge_seconds
CHALLENGE_PREFIX = "challenge:"


def _challenge_key(verification_id: uuid.UUID) -> str:
    return f"{CHALLENGE_PREFIX}{verification_id}"


def build_message(verification_id: uuid.UUID, nonce: str, decision: str) -> str:
    # Le message signé lie la signature à CETTE demande, à CE défi et à CETTE décision.
    return f"echoshield:v1:{verification_id}:{nonce}:{decision}"


def _out(v: VerificationRequest) -> VerificationOut:
    return VerificationOut(
        id=v.id,
        circle_id=v.circle_id,
        requester_id=v.requester_id,
        claimed_user_id=v.claimed_user_id,
        note=v.note,
        status=v.status,
        created_at=v.created_at,
        expires_at=v.expires_at,
        responded_at=v.responded_at,
        risk=RiskReportOut.from_report(analyze(v.note)),
    )


async def _get_member(db: AsyncSession, circle_id: uuid.UUID, user_id: uuid.UUID) -> CircleMember | None:
    return await db.scalar(
        select(CircleMember).where(
            CircleMember.circle_id == circle_id,
            CircleMember.user_id == user_id,
        )
    )


def _expire_if_needed(v: VerificationRequest, now: datetime) -> bool:
    if v.status == VerificationStatus.PENDING and v.expires_at <= now:
        v.status = VerificationStatus.EXPIRED
        return True
    return False


@router.post("", response_model=VerificationOut, status_code=status.HTTP_201_CREATED)
async def create_verification(
    data: VerificationCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationOut:
    if data.claimed_user_id == current_user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Vous ne pouvez pas vérifier un appel venant de vous-même")
    if await _get_member(db, data.circle_id, current_user.id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cercle introuvable")
    if await _get_member(db, data.circle_id, data.claimed_user_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ce contact ne fait pas partie du cercle")

    now = datetime.now(timezone.utc)
    verification_id = uuid.uuid4()
    nonce = secrets.token_urlsafe(32)

    # Le défi vit uniquement dans Redis et disparaît tout seul après 2 minutes.
    await redis_client.set(_challenge_key(verification_id), nonce, ex=CHALLENGE_SECONDS)

    verification = VerificationRequest(
        id=verification_id,
        circle_id=data.circle_id,
        requester_id=current_user.id,
        claimed_user_id=data.claimed_user_id,
        note=data.note.strip() if data.note else None,
        status=VerificationStatus.PENDING,
        expires_at=now + timedelta(seconds=CHALLENGE_SECONDS),
    )
    db.add(verification)
    await db.commit()
    await db.refresh(verification)
    return _out(verification)


# Déclarée AVANT /{verification_id}, sinon FastAPI prendrait « incoming » pour un identifiant.
@router.get("/incoming", response_model=list[IncomingChallenge])
async def list_incoming(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[IncomingChallenge]:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(VerificationRequest, User.full_name)
        .join(User, User.id == VerificationRequest.requester_id)
        .where(
            VerificationRequest.claimed_user_id == current_user.id,
            VerificationRequest.status == VerificationStatus.PENDING,
            VerificationRequest.expires_at > now,
        )
        .order_by(VerificationRequest.created_at)
    )

    challenges = []
    for verification, requester_name in result.all():
        nonce = await redis_client.get(_challenge_key(verification.id))
        if nonce is None:
            continue
        challenges.append(
            IncomingChallenge(
                id=verification.id,
                requester_name=requester_name,
                note=verification.note,
                expires_at=verification.expires_at,
                message_to_sign_confirm=build_message(verification.id, nonce, "confirm"),
                message_to_sign_deny=build_message(verification.id, nonce, "deny"),
            )
        )
    return challenges


@router.get("/{verification_id}", response_model=VerificationOut)
async def get_verification(
    verification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationOut:
    verification = await db.get(VerificationRequest, verification_id)
    if verification is None or current_user.id not in (
        verification.requester_id,
        verification.claimed_user_id,
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demande introuvable")

    if _expire_if_needed(verification, datetime.now(timezone.utc)):
        await db.commit()
    return _out(verification)


@router.post("/{verification_id}/respond", response_model=VerificationOut)
async def respond_to_verification(
    verification_id: uuid.UUID,
    data: VerificationAnswer,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerificationOut:
    now = datetime.now(timezone.utc)

    verification = await db.scalar(
        select(VerificationRequest)
        .where(VerificationRequest.id == verification_id)
        .with_for_update()
    )
    if verification is None or verification.claimed_user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demande introuvable")

    if _expire_if_needed(verification, now):
        await db.commit()
        raise HTTPException(status.HTTP_410_GONE, "Défi expiré : la demande reste non vérifiée")
    if verification.status != VerificationStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette demande a déjà reçu une réponse")

    device = await db.scalar(
        select(Device).where(Device.id == data.device_id, Device.user_id == current_user.id)
    )
    if device is None or not device.can_confirm(now):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cet appareil n'est pas autorisé à répondre")

    if data.decision == "confirm":
        member = await _get_member(db, verification.circle_id, current_user.id)
        if member is None or member.trusted_from > now:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Vous n'êtes pas encore membre de confiance de ce cercle",
            )

    key = _challenge_key(verification.id)
    nonce = await redis_client.get(key)
    if nonce is None:
        verification.status = VerificationStatus.EXPIRED
        await db.commit()
        raise HTTPException(status.HTTP_410_GONE, "Défi expiré : la demande reste non vérifiée")

    message = build_message(verification.id, nonce, data.decision).encode()
    if not verify_signature(device.public_key, message, data.signature):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Signature invalide")

    # Le défi est consommé : il ne pourra jamais resservir.
    if await redis_client.delete(key) == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce défi a déjà été utilisé")

    verification.status = (
        VerificationStatus.CONFIRMED if data.decision == "confirm" else VerificationStatus.DENIED
    )
    verification.responded_at = now
    verification.responding_device_id = device.id
    device.last_seen_at = now
    await db.commit()
    return _out(verification)
