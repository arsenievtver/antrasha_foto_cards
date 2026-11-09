"""Клиенты А на контроле: список, история недель, сотрудники и комментарии."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AdminPrincipal, require_superuser
from app.schemas.a_clients import (
    AClientDetailOut,
    AClientListOut,
    AClientSyncOut,
    ActiveBoardOut,
    CaretakerIn,
    CaretakerOut,
)
from app.services.a_client_active import load_active_board
from app.services.a_clients import (
    add_caretaker,
    dismiss_caretaker,
    get_client,
    list_clients,
    refresh_from_reports,
)

router = APIRouter(prefix="/admin/a-clients", tags=["admin-a-clients"])


@router.get("", response_model=AClientListOut)
def list_a_clients(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
    q: str | None = Query(None),
    status: str | None = Query(None),
    active: bool | None = Query(None),
    caretaker: str | None = Query(None),
    without_caretaker: bool = Query(False),
) -> dict:
    items = list_clients(
        db,
        q=q,
        status=status,
        active=active,
        caretaker=caretaker,
        without_caretaker=without_caretaker,
    )
    return {"items": items, "total": len(items)}


@router.post("/sync", response_model=AClientSyncOut)
def sync_a_clients(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
) -> dict:
    stats = refresh_from_reports(db)
    db.commit()
    return stats


@router.get("/active", response_model=ActiveBoardOut)
def active_a_clients(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
) -> dict:
    return load_active_board(db)


@router.get("/{client_id}", response_model=AClientDetailOut)
def get_a_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
) -> dict:
    row = get_client(db, client_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    return row


@router.post("/{client_id}/caretakers", response_model=CaretakerOut, status_code=201)
def create_caretaker(
    client_id: uuid.UUID,
    body: CaretakerIn,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
) -> dict:
    try:
        row = add_caretaker(
            db,
            client_id,
            author_user_id=body.author_user_id,
            author_label=body.author_label,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "author_user_id": row.author_user_id,
        "author_label": row.author_label,
        "source": row.source,
        "active": row.active,
        "created_at": row.created_at,
    }


@router.delete("/{client_id}/caretakers/{caretaker_id}", status_code=204)
def delete_caretaker(
    client_id: uuid.UUID,
    caretaker_id: uuid.UUID,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
) -> None:
    try:
        dismiss_caretaker(db, client_id, caretaker_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
