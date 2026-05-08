import uuid
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, UserSession
from app.security import decode_token_payload, decode_token_user_id

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AdminPrincipal:
    role: Literal["superuser", "worker"]
    user: User | None


def get_optional_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User | None:
    if not credentials or credentials.scheme.lower() != "bearer":
        return None

    uid = decode_token_user_id(credentials.credentials)
    if uid is None:
        return None
    return db.get(User, uid)


def require_user(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    uid = decode_token_user_id(credentials.credentials)
    if uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.get(User, uid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def parse_session_id(x_session_id: str | None = Header(None, alias="X-Session-Id")) -> uuid.UUID:
    if not x_session_id or not x_session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header X-Session-Id is required",
        )
    try:
        return uuid.UUID(x_session_id.strip())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Session-Id",
        ) from e


def get_session_or_404(
    db: Session,
    session_id: uuid.UUID,
) -> UserSession:
    s = db.get(UserSession, session_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return s


def get_admin_principal(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AdminPrincipal:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
        )
    parsed = decode_token_payload(credentials.credentials)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    uid, role = parsed
    if role == "superuser":
        return AdminPrincipal(role="superuser", user=None)
    if role != UserRole.worker.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access requires worker or superuser role",
        )
    if uid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    user = db.get(User, uid)
    if not user or user.role != UserRole.worker.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Worker privileges required",
        )
    return AdminPrincipal(role="worker", user=user)


def require_superuser(
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPrincipal:
    if principal.role != "superuser":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser only",
        )
    return principal
