import uuid

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.redis import redis_client
from app.core.security import (
    DUMMY_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

REFRESH_PREFIX = "refresh:"


async def _issue_tokens(user_id: uuid.UUID) -> TokenPair:
    access_token = create_access_token(user_id)
    refresh_token, jti = create_refresh_token(user_id)
    await redis_client.set(
        f"{REFRESH_PREFIX}{jti}",
        str(user_id),
        ex=settings.refresh_token_days * 86400,
    )
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)) -> User:
    user = User(
        email=data.email.lower(),
        full_name=data.full_name.strip(),
        password_hash=hash_password(data.password),
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cet e-mail")
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    user = await db.scalar(select(User).where(User.email == data.email.lower()))

    password_ok = verify_password(data.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not password_ok or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou mot de passe incorrect")

    return await _issue_tokens(user.id)


@router.post("/refresh", response_model=TokenPair)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)) -> TokenPair:
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton invalide, expiré ou déjà utilisé")

    try:
        payload = decode_token(data.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise invalid

    # GETDEL lit et supprime en une seule opération : un jeton ne sert qu'une fois.
    stored_user_id = await redis_client.getdel(f"{REFRESH_PREFIX}{payload['jti']}")
    if stored_user_id is None:
        raise invalid

    user = await db.get(User, uuid.UUID(stored_user_id))
    if user is None or not user.is_active:
        raise invalid

    return await _issue_tokens(user.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(data: RefreshRequest) -> None:
    try:
        payload = decode_token(data.refresh_token, "refresh")
    except jwt.PyJWTError:
        return
    await redis_client.delete(f"{REFRESH_PREFIX}{payload['jti']}")


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user