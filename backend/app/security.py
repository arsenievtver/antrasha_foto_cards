import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def hash_pin(pin: str) -> str:
    """Bcrypt-хеш PIN/пароля (совместим со строками `$2b$...`, раньше создававшимися через passlib)."""
    digest = bcrypt.hashpw(pin.encode("utf-8"), bcrypt.gensalt())
    return digest.decode("ascii")


def verify_pin(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.strip().encode("ascii"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    *,
    user_id: uuid.UUID | None = None,
    role: str = "user",
) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload: dict = {"exp": expire, "role": role}
    if role == "superuser":
        payload["sub"] = "superuser"
    elif user_id is not None:
        payload["sub"] = str(user_id)
    else:
        raise ValueError("user_id required unless role is superuser")
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token_payload(token: str) -> tuple[uuid.UUID | None, str] | None:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        role = str(payload.get("role") or "user")
        sub = payload.get("sub")
        if role == "superuser" or sub == "superuser":
            return (None, "superuser")
        if not sub:
            return None
        return (uuid.UUID(str(sub)), role)
    except (JWTError, ValueError):
        return None


def decode_token_user_id(token: str) -> uuid.UUID | None:
    parsed = decode_token_payload(token)
    if parsed is None:
        return None
    uid, _role = parsed
    return uid
