import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

settings = get_settings()
_hasher = PasswordHasher()

# Hash factice : utilisé quand l'e-mail n'existe pas, pour que la réponse
# prenne le même temps et ne révèle pas si un compte existe.
DUMMY_HASH = _hasher.hash("echoshield-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _create_token(user_id: uuid.UUID, token_type: str, lifetime: timedelta) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    jti = uuid.uuid4().hex
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": now + lifetime,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, jti


def create_access_token(user_id: uuid.UUID) -> str:
    token, _ = _create_token(user_id, "access", timedelta(minutes=settings.access_token_minutes))
    return token


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, str]:
    return _create_token(user_id, "refresh", timedelta(days=settings.refresh_token_days))


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("Type de jeton invalide")
    return payload