"""Выпуск и проверка ключей MCP закупок.

Ключ живёт дольше JWT админки и отзывается сразу: каждый запрос MCP сверяет
хэш с таблицей. Открытый текст хранится, чтобы экран в админке мог показать
его снова — как только ключ отозван, текст стирается.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.deps import AdminPrincipal
from app.models.mcp_api_key import (
    OWNER_SUPERUSER,
    OWNER_WORKER,
    SCOPE_READ,
    SCOPE_WRITE,
    McpApiKey,
)
from app.models.user import User, UserRole
from app.permissions import effective_worker_permissions

KEY_PREFIX = "mcp_live_"
TAIL_LENGTH = 4
SCOPES = (SCOPE_READ, SCOPE_WRITE)
TOUCH_THROTTLE = timedelta(minutes=1)
PRODUCT_PERMISSION = "product"


@dataclass(frozen=True)
class McpActor:
    key_id: uuid.UUID
    owner_role: str
    user_id: uuid.UUID | None
    scope: str


def generate_key() -> str:
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def mask_key(key: McpApiKey) -> str:
    return f"{KEY_PREFIX}…{key.key_tail}"


def is_active(key: McpApiKey) -> bool:
    if key.revoked_at is not None:
        return False
    if key.expires_at is not None and key.expires_at <= datetime.now(timezone.utc):
        return False
    return True


def _owner_filter(principal: AdminPrincipal):
    if principal.role == "superuser":
        return (
            McpApiKey.owner_role == OWNER_SUPERUSER,
            McpApiKey.user_id.is_(None),
        )
    return (McpApiKey.user_id == principal.user.id,)


def owns_key(principal: AdminPrincipal, key: McpApiKey) -> bool:
    if principal.role == "superuser":
        return key.owner_role == OWNER_SUPERUSER and key.user_id is None
    return principal.user is not None and key.user_id == principal.user.id


def get_key_by_id(db: Session, key_id: uuid.UUID) -> McpApiKey | None:
    return db.get(McpApiKey, key_id)


def get_active_key_for_principal(db: Session, principal: AdminPrincipal) -> McpApiKey | None:
    now = datetime.now(timezone.utc)
    stmt = (
        select(McpApiKey)
        .where(
            *_owner_filter(principal),
            McpApiKey.revoked_at.is_(None),
            or_(McpApiKey.expires_at.is_(None), McpApiKey.expires_at > now),
        )
        .order_by(McpApiKey.created_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()


def _new_row(
    principal: AdminPrincipal,
    name: str,
    scope: str,
    plaintext: str,
) -> McpApiKey:
    if principal.role == "superuser":
        owner_role = OWNER_SUPERUSER
        user_id = None
    else:
        owner_role = OWNER_WORKER
        user_id = principal.user.id
    return McpApiKey(
        user_id=user_id,
        owner_role=owner_role,
        name=name.strip() or "MCP клиент",
        key_hash=hash_key(plaintext),
        key_tail=plaintext[-TAIL_LENGTH:],
        key_plain=plaintext,
        scope=scope,
    )


def issue_key(
    db: Session,
    principal: AdminPrincipal,
    name: str,
    scope: str = SCOPE_READ,
) -> tuple[McpApiKey, str]:
    plaintext = generate_key()
    key = _new_row(principal, name, scope, plaintext)
    db.add(key)
    db.commit()
    db.refresh(key)
    return key, plaintext


def revoke_key(db: Session, key: McpApiKey) -> McpApiKey:
    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        key.key_plain = None
        db.commit()
        db.refresh(key)
    return key


def rotate_key(
    db: Session, key: McpApiKey, principal: AdminPrincipal
) -> tuple[McpApiKey, str]:
    """Старый ключ гаснет в той же транзакции, что и выпуск нового.

    Сначала помечаем старый отозванным и сбрасываем flush: частичный уникальный
    индекс не пустит второй активный ключ того же владельца.
    """
    plaintext = generate_key()
    key.revoked_at = datetime.now(timezone.utc)
    key.key_plain = None
    db.flush()
    new_key = _new_row(principal, key.name, key.scope, plaintext)
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    return new_key, plaintext


def resolve_key(db: Session, plaintext: str) -> McpApiKey | None:
    if not plaintext.startswith(KEY_PREFIX):
        return None
    key = db.scalars(
        select(McpApiKey).where(McpApiKey.key_hash == hash_key(plaintext))
    ).first()
    if key is None or not is_active(key):
        return None
    if key.owner_role == OWNER_SUPERUSER:
        return key
    user = db.get(User, key.user_id)
    if user is None or user.role != UserRole.worker.value:
        return None
    if PRODUCT_PERMISSION not in effective_worker_permissions(user.admin_permissions):
        return None
    return key


def actor_from_key(key: McpApiKey) -> McpActor:
    return McpActor(
        key_id=key.id,
        owner_role=key.owner_role,
        user_id=key.user_id,
        scope=key.scope,
    )


def touch_key(db: Session, key: McpApiKey) -> None:
    now = datetime.now(timezone.utc)
    if key.last_used_at is not None and now - key.last_used_at < TOUCH_THROTTLE:
        return
    key.last_used_at = now
    db.commit()
