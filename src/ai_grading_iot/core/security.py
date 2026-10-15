from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError

from ai_grading_iot.core.config import get_settings


_hasher = PasswordHasher(type=Type.ID)
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _jwt_secret() -> str:
    secret = get_settings().JWT_SECRET_KEY
    if not secret or len(secret.encode("utf-8")) < 32:
        raise RuntimeError("JWT_SECRET_KEY phải được cấu hình với ít nhất 32 byte.")
    return secret


def create_access_token(user_id: UUID) -> tuple[str, int]:
    expires_in = get_settings().JWT_ACCESS_TOKEN_EXPIRE_SECONDS
    if expires_in < 1:
        raise RuntimeError("JWT_ACCESS_TOKEN_EXPIRE_SECONDS phải lớn hơn 0.")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_ALGORITHM), expires_in


def decode_access_token(token: str) -> UUID:
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[_ALGORITHM],
            options={"require": ["sub", "type", "iat", "exp"]},
        )
        if payload["type"] != "access":
            raise ValueError("Invalid token type")
        return UUID(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError) as exc:
        raise ValueError("Invalid access token") from exc
