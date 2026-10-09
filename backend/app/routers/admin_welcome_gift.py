"""Админка: акция «сертификат за регистрацию, PWA и push»."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AdminPrincipal, require_permission
from app.models.welcome_gift_settings import WelcomeGiftSettings
from app.schemas.welcome_gift import WelcomeGiftSettingsOut, WelcomeGiftSettingsPut

router = APIRouter(prefix="/admin/welcome-gift", tags=["admin-welcome-gift"])


def _row_or_create(db: Session) -> WelcomeGiftSettings:
    row = db.get(WelcomeGiftSettings, 1)
    if row is not None:
        return row
    row = WelcomeGiftSettings(id=1, enabled=False, nominal=0, period_days=30)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _out(row: WelcomeGiftSettings) -> WelcomeGiftSettingsOut:
    return WelcomeGiftSettingsOut(
        enabled=row.enabled,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        nominal=float(row.nominal or 0),
        period_days=int(row.period_days or 30),
    )


@router.get("", response_model=WelcomeGiftSettingsOut)
def get_welcome_gift_settings(
    db: Session = Depends(get_db),
    _: AdminPrincipal = Depends(require_permission("ads")),
) -> WelcomeGiftSettingsOut:
    return _out(_row_or_create(db))


@router.put("", response_model=WelcomeGiftSettingsOut)
def put_welcome_gift_settings(
    body: WelcomeGiftSettingsPut,
    db: Session = Depends(get_db),
    _: AdminPrincipal = Depends(require_permission("ads")),
) -> WelcomeGiftSettingsOut:
    if body.enabled and body.valid_from is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите дату начала акции",
        )
    if body.enabled and body.nominal <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите сумму сертификата",
        )
    if (
        body.valid_from is not None
        and body.valid_to is not None
        and body.valid_to < body.valid_from
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата окончания раньше даты начала",
        )
    row = _row_or_create(db)
    row.enabled = body.enabled
    row.valid_from = body.valid_from
    row.valid_to = body.valid_to
    row.nominal = body.nominal
    row.period_days = body.period_days
    db.commit()
    db.refresh(row)
    return _out(row)
