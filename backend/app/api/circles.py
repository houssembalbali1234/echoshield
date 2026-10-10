import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import Circle, CircleMember, CircleRole, Invitation, User
from app.schemas.circle import (
    AcceptInvitation,
    CircleCreate,
    CircleDetail,
    CircleOut,
    InvitationCreated,
    MemberOut,
)

router = APIRouter(tags=["circles"])

INVITATION_HOURS = 48
TRUST_DELAY_HOURS = 24
MANAGER_ROLES = (CircleRole.OWNER, CircleRole.ADMIN)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _circle_out(circle: Circle, role: CircleRole) -> CircleOut:
    return CircleOut(
        id=circle.id,
        name=circle.name,
        kind=circle.kind,
        created_at=circle.created_at,
        my_role=role,
    )


async def _get_membership(db: AsyncSession, circle_id: uuid.UUID, user_id: uuid.UUID) -> CircleMember:
    membership = await db.scalar(
        select(CircleMember).where(
            CircleMember.circle_id == circle_id,
            CircleMember.user_id == user_id,
        )
    )
    if membership is None:
        # 404 plutôt que 403 : on ne révèle pas l'existence d'un cercle dont on n'est pas membre.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cercle introuvable")
    return membership


@router.post("/circles", response_model=CircleOut, status_code=status.HTTP_201_CREATED)
async def create_circle(
    data: CircleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CircleOut:
    circle = Circle(name=data.name.strip(), kind=data.kind, created_by_id=current_user.id)
    circle.members.append(
        CircleMember(
            user_id=current_user.id,
            role=CircleRole.OWNER,
            trusted_from=datetime.now(timezone.utc),
        )
    )
    db.add(circle)
    await db.commit()
    await db.refresh(circle)
    return _circle_out(circle, CircleRole.OWNER)


@router.get("/circles", response_model=list[CircleOut])
async def list_circles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CircleOut]:
    result = await db.execute(
        select(Circle, CircleMember.role)
        .join(CircleMember, CircleMember.circle_id == Circle.id)
        .where(CircleMember.user_id == current_user.id)
        .order_by(Circle.created_at)
    )
    return [_circle_out(circle, role) for circle, role in result.all()]


@router.get("/circles/{circle_id}", response_model=CircleDetail)
async def get_circle(
    circle_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CircleDetail:
    membership = await _get_membership(db, circle_id, current_user.id)
    circle = await db.get(Circle, circle_id)

    result = await db.execute(
        select(CircleMember, User)
        .join(User, User.id == CircleMember.user_id)
        .where(CircleMember.circle_id == circle_id)
        .order_by(CircleMember.created_at)
    )
    now = datetime.now(timezone.utc)
    members = [
        MemberOut(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=member.role,
            trusted_from=member.trusted_from,
            is_trusted=member.trusted_from <= now,
        )
        for member, user in result.all()
    ]
    return CircleDetail(**_circle_out(circle, membership.role).model_dump(), members=members)


@router.post(
    "/circles/{circle_id}/invitations",
    response_model=InvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    circle_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvitationCreated:
    membership = await _get_membership(db, circle_id, current_user.id)
    if membership.role not in MANAGER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seuls le propriétaire et les administrateurs peuvent inviter")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=INVITATION_HOURS)
    db.add(
        Invitation(
            circle_id=circle_id,
            created_by_id=current_user.id,
            token_hash=_hash_token(token),
            expires_at=expires_at,
        )
    )
    await db.commit()

    # Le jeton en clair n'est renvoyé qu'une seule fois, ici. Il n'est jamais stocké.
    return InvitationCreated(token=token, expires_at=expires_at)


@router.post("/invitations/accept", response_model=CircleOut)
async def accept_invitation(
    data: AcceptInvitation,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CircleOut:
    invitation = await db.scalar(
        select(Invitation)
        .where(Invitation.token_hash == _hash_token(data.token))
        .with_for_update()
    )
    now = datetime.now(timezone.utc)
    if invitation is None or invitation.accepted_at is not None or invitation.expires_at <= now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invitation invalide, expirée ou déjà utilisée")

    already_member = await db.scalar(
        select(CircleMember).where(
            CircleMember.circle_id == invitation.circle_id,
            CircleMember.user_id == current_user.id,
        )
    )
    if already_member:
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous êtes déjà membre de ce cercle")

    invitation.accepted_at = now
    invitation.accepted_by_id = current_user.id
    db.add(
        CircleMember(
            circle_id=invitation.circle_id,
            user_id=current_user.id,
            role=CircleRole.MEMBER,
            trusted_from=now + timedelta(hours=TRUST_DELAY_HOURS),
        )
    )
    await db.commit()

    circle = await db.get(Circle, invitation.circle_id)
    return _circle_out(circle, CircleRole.MEMBER)


@router.delete("/circles/{circle_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    circle_id: uuid.UUID,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    my_membership = await _get_membership(db, circle_id, current_user.id)

    target = await db.scalar(
        select(CircleMember).where(
            CircleMember.circle_id == circle_id,
            CircleMember.user_id == user_id,
        )
    )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membre introuvable")
    if target.role == CircleRole.OWNER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le propriétaire ne peut pas être retiré")

    leaving_myself = user_id == current_user.id
    if not leaving_myself and my_membership.role not in MANAGER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Vous ne pouvez pas retirer ce membre")

    await db.delete(target)
    await db.commit()