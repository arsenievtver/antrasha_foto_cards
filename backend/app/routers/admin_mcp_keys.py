"""Ключ MCP закупок для текущего администратора.

Один активный ключ на владельца: у суперпользователя общий (у учётки нет
строки в users), у сотрудника — свой. Чужой ключ отвечает 404.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AdminPrincipal, require_permission
from app.schemas.mcp_keys import (
    McpKeyCreateInput,
    McpKeyCreated,
    McpKeyRead,
    serialize_created_key,
    serialize_key,
)
from app.services.mcp_keys import (
    get_active_key_for_principal,
    get_key_by_id,
    issue_key,
    owns_key,
    revoke_key,
    rotate_key,
)

router = APIRouter(prefix="/admin/mcp-keys", tags=["admin-mcp-keys"])


def _own_key(
    key_id: uuid.UUID,
    principal: AdminPrincipal,
    db: Session,
):
    key = get_key_by_id(db, key_id)
    if key is None or not owns_key(principal, key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ключ не найден")
    if key.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ключ не найден")
    return key


@router.get("/my", response_model=McpKeyRead | None)
def get_my_key(
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_permission("product")),
) -> McpKeyRead | None:
    key = get_active_key_for_principal(db, principal)
    return None if key is None else serialize_key(key)


@router.post("", response_model=McpKeyCreated, status_code=status.HTTP_201_CREATED)
def create_key(
    body: McpKeyCreateInput,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_permission("product")),
) -> McpKeyCreated:
    existing = get_active_key_for_principal(db, principal)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="У вас уже есть активный ключ. Обновите его или отзовите.",
        )
    try:
        key, plaintext = issue_key(db, principal, body.name, body.scope)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="У вас уже есть активный ключ. Обновите его или отзовите.",
        ) from None
    return serialize_created_key(key, plaintext)


@router.post("/{key_id}/rotate", response_model=McpKeyCreated)
def rotate(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_permission("product")),
) -> McpKeyCreated:
    key = _own_key(key_id, principal, db)
    new_key, plaintext = rotate_key(db, key, principal)
    return serialize_created_key(new_key, plaintext)


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_permission("product")),
) -> Response:
    key = _own_key(key_id, principal, db)
    revoke_key(db, key)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
