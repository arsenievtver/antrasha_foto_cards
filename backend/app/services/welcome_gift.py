"""Сертификат новому клиенту: регистрация в период акции, PWA и push."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.gift_certificate import GiftCertificate, GiftCertificateStatus
from app.models.push_subscription import PushSubscription
from app.models.user import User, UserRole
from app.models.welcome_gift_settings import WelcomeGiftSettings
from app.services.gift_certificates import (
    allocate_code,
    allocate_public_slug,
    certificate_link,
    new_ulid,
    set_actual_status,
)
from app.services.web_push import send_push_to_user

log = logging.getLogger("app.welcome_gift")

TZ = ZoneInfo("Europe/Moscow")
WELCOME_EMPLOYEE = "Акция приложения"


def moscow_today() -> date:
    return datetime.now(TZ).date()


def period_covers(row: WelcomeGiftSettings, day: date) -> bool:
    if row.valid_from is None or day < row.valid_from:
        return False
    if row.valid_to is not None and day > row.valid_to:
        return False
    return True


def registration_day(user: User) -> date:
    moment = user.created_at
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(TZ).date()


def issued_out(cert: GiftCertificate) -> dict:
    return {
        "code": cert.code,
        "amount": cert.amount,
        "url": certificate_link(cert.public_slug),
    }


def _rub(amount: float) -> str:
    if float(amount).is_integer():
        return str(int(amount))
    return f"{amount:.2f}".rstrip("0").rstrip(".")


def maybe_issue_welcome_gift(
    db: Session,
    user: User | None,
    *,
    pwa_standalone: bool,
) -> GiftCertificate | None:
    """Один сертификат на аккаунт. None — условия акции не сошлись."""
    if user is None or not pwa_standalone:
        return None
    if user.role != UserRole.user.value:
        return None

    locked = db.execute(
        select(User).where(User.id == user.id).with_for_update()
    ).scalar_one()
    if locked.welcome_gift_cert_id:
        return None

    row = db.get(WelcomeGiftSettings, 1)
    if row is None or not row.enabled:
        return None
    if row.nominal <= 0 or row.period_days < 1:
        return None

    today = moscow_today()
    if not period_covers(row, today) or not period_covers(row, registration_day(locked)):
        return None

    db.flush()
    has_push = db.scalar(
        select(PushSubscription.id).where(
            PushSubscription.user_id == locked.id,
            PushSubscription.is_active.is_(True),
        )
    )
    if has_push is None:
        return None

    cert = GiftCertificate(
        id=new_ulid(),
        code=allocate_code(db),
        public_slug=allocate_public_slug(db),
        nominal=row.nominal,
        amount=row.nominal,
        description="За регистрацию, установку приложения и уведомления",
        employee=WELCOME_EMPLOYEE,
        status=GiftCertificateStatus.ACTIVE.value,
        created_at=today,
        indefinite=False,
        period=row.period_days,
        name=(locked.display_name or "").strip() or None,
        phone=locked.phone,
    )
    set_actual_status(cert, today)
    db.add(cert)
    db.flush()
    locked.welcome_gift_cert_id = cert.id
    log.info(
        "welcome gift %s for user %s nominal=%s period=%s",
        cert.code,
        locked.id,
        row.nominal,
        row.period_days,
    )
    return cert


def notify_welcome_gift(db: Session, cert: GiftCertificate) -> None:
    user = db.execute(select(User).where(User.phone == cert.phone)).scalar_one_or_none()
    if user is None:
        return
    link = certificate_link(cert.public_slug)
    send_push_to_user(
        db,
        user_id=user.id,
        settings=settings,
        title="Подарочный сертификат",
        body=f"Вам сертификат ANTRASHA на {_rub(cert.amount)} ₽. Открыть: {link}",
        url=link,
        tag=f"welcome-gift-{cert.public_slug}",
    )
