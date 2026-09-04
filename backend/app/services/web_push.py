"""Web Push: подписки и рассылка «новинки» (не чаще раза в сутки на подписку)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from pywebpush import WebPushException, webpush
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PushSubscription
from app.models.push_subscription import (
    PUSH_GENDER_BOTH,
    PUSH_GENDER_FEMALE,
    PUSH_GENDER_MALE,
    PUSH_GENDER_SCOPES,
)

log = logging.getLogger("app.web_push")

NOTIFY_COOLDOWN = timedelta(hours=24)
NOTIFICATION_TAG = "antrasha-new-photos"


def web_push_configured(settings: Settings) -> bool:
    return bool(
        settings.vapid_public_key
        and str(settings.vapid_public_key).strip()
        and settings.vapid_private_key
        and str(settings.vapid_private_key).strip()
        and settings.vapid_claims_sub
        and str(settings.vapid_claims_sub).strip()
    )


def format_new_photos_message(count: int) -> tuple[str, str]:
    n = max(1, int(count))
    mod100 = n % 100
    mod10 = n % 10
    if 11 <= mod100 <= 14:
        phrase = f"{n} новых образов"
    elif mod10 == 1:
        phrase = f"{n} новый образ"
    elif 2 <= mod10 <= 4:
        phrase = f"{n} новых образа"
    else:
        phrase = f"{n} новых образов"
    return f"{phrase} — оцените новинки", ""


def merge_session_push_subscriptions(
    db: Session,
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    db.execute(
        update(PushSubscription)
        .where(PushSubscription.session_id == session_id)
        .values(user_id=user_id, session_id=None)
    )


def upsert_push_subscription(
    db: Session,
    *,
    endpoint: str,
    p256dh: str,
    auth: str,
    session_id: uuid.UUID,
    user_id: uuid.UUID | None,
    gender_scope: str = PUSH_GENDER_BOTH,
) -> PushSubscription:
    scope = gender_scope if gender_scope in PUSH_GENDER_SCOPES else PUSH_GENDER_BOTH
    row = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    ).scalar_one_or_none()
    if row:
        row.p256dh = p256dh
        row.auth = auth
        row.gender_scope = scope
        row.is_active = True
        if user_id is not None:
            row.user_id = user_id
            row.session_id = None
        else:
            row.session_id = session_id
        return row
    sub = PushSubscription(
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        session_id=None if user_id else session_id,
        user_id=user_id,
        gender_scope=scope,
        is_active=True,
    )
    db.add(sub)
    return sub


def deactivate_push_subscription(db: Session, endpoint: str) -> None:
    row = db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == endpoint)
    ).scalar_one_or_none()
    if row:
        row.is_active = False


def _subscription_info(row: PushSubscription) -> dict:
    return {
        "endpoint": row.endpoint,
        "keys": {"p256dh": row.p256dh, "auth": row.auth},
    }


def _send_one(
    row: PushSubscription,
    *,
    settings: Settings,
    payload: dict,
) -> bool:
    try:
        webpush(
            subscription_info=_subscription_info(row),
            data=json.dumps(payload, ensure_ascii=False),
            vapid_private_key=settings.vapid_private_key.strip(),
            vapid_claims={"sub": settings.vapid_claims_sub.strip()},
        )
        return True
    except WebPushException as ex:
        status = ex.response.status_code if ex.response is not None else None
        if status in (404, 410):
            row.is_active = False
            log.info("web_push: подписка %s деактивирована (HTTP %s)", row.id, status)
        else:
            log.warning(
                "web_push: ошибка отправки подписке %s: %s",
                row.id,
                ex,
            )
        return False
    except Exception:
        log.exception("web_push: неожиданная ошибка для подписки %s", row.id)
        return False


def _new_photos_count_for_scope(
    gender_scope: str,
    *,
    rows_added_male: int,
    rows_added_female: int,
) -> int:
    if gender_scope == PUSH_GENDER_MALE:
        return max(0, rows_added_male)
    if gender_scope == PUSH_GENDER_FEMALE:
        return max(0, rows_added_female)
    return max(0, rows_added_male + rows_added_female)


def _notification_url_for_scope(settings: Settings, gender_scope: str) -> str:
    base = settings.public_app_url.rstrip("/")
    if gender_scope == PUSH_GENDER_MALE:
        return f"{base}/swipe/male"
    if gender_scope == PUSH_GENDER_FEMALE:
        return f"{base}/swipe/female"
    return f"{base}/"


def notify_new_photos_if_due(
    db: Session,
    *,
    settings: Settings,
    rows_added_male: int,
    rows_added_female: int,
) -> dict[str, int]:
    """
    Отправляет push подписчикам, у которых не было уведомления ≥24 ч
    и появились новинки в выбранной категории (муж / жен / обе).
    """
    if rows_added_male <= 0 and rows_added_female <= 0:
        return {"eligible": 0, "sent": 0, "failed": 0, "skipped_scope": 0}
    if not web_push_configured(settings):
        log.debug("web_push: VAPID не задан — пропуск уведомлений")
        return {"eligible": 0, "sent": 0, "failed": 0, "skipped_scope": 0}

    now = datetime.now(timezone.utc)
    cutoff = now - NOTIFY_COOLDOWN
    rows = list(
        db.execute(
            select(PushSubscription).where(
                PushSubscription.is_active.is_(True),
                or_(
                    PushSubscription.last_notified_at.is_(None),
                    PushSubscription.last_notified_at < cutoff,
                ),
            )
        ).scalars()
    )
    if not rows:
        return {"eligible": 0, "sent": 0, "failed": 0, "skipped_scope": 0}

    sent = 0
    failed = 0
    skipped_scope = 0
    for row in rows:
        count = _new_photos_count_for_scope(
            row.gender_scope,
            rows_added_male=rows_added_male,
            rows_added_female=rows_added_female,
        )
        if count <= 0:
            skipped_scope += 1
            continue

        title, body = format_new_photos_message(count)
        payload = {
            "title": title,
            "body": body,
            "url": _notification_url_for_scope(settings, row.gender_scope),
            "tag": NOTIFICATION_TAG,
        }
        if _send_one(row, settings=settings, payload=payload):
            row.last_notified_at = now
            sent += 1
        else:
            failed += 1

    db.commit()
    log.info(
        "web_push: male+%s female+%s eligible=%s sent=%s failed=%s skipped_scope=%s",
        rows_added_male,
        rows_added_female,
        len(rows),
        sent,
        failed,
        skipped_scope,
    )
    return {
        "eligible": len(rows),
        "sent": sent,
        "failed": failed,
        "skipped_scope": skipped_scope,
    }


def maybe_notify_after_photo_sync(
    settings: Settings,
    *,
    rows_added_male: int,
    rows_added_female: int,
) -> None:
    """
    Авто-рассылка после синка фото отключена: партии загрузок дают лишний спам.
    Рассылка — вручную из админки (broadcast_admin_push).
    """
    _ = (settings, rows_added_male, rows_added_female)
    return


def push_subscription_stats(db: Session) -> dict[str, int]:
    rows = list(
        db.execute(
            select(PushSubscription).where(PushSubscription.is_active.is_(True))
        ).scalars()
    )
    male = sum(1 for r in rows if r.gender_scope == PUSH_GENDER_MALE)
    female = sum(1 for r in rows if r.gender_scope == PUSH_GENDER_FEMALE)
    both = sum(1 for r in rows if r.gender_scope == PUSH_GENDER_BOTH)
    return {
        "active_total": len(rows),
        "active_male": male,
        "active_female": female,
        "active_both": both,
    }


def _audience_matches(row_scope: str, audience: str) -> bool:
    if audience == "all":
        return True
    if audience == PUSH_GENDER_MALE:
        return row_scope in (PUSH_GENDER_MALE, PUSH_GENDER_BOTH)
    if audience == PUSH_GENDER_FEMALE:
        return row_scope in (PUSH_GENDER_FEMALE, PUSH_GENDER_BOTH)
    if audience == PUSH_GENDER_BOTH:
        return row_scope == PUSH_GENDER_BOTH
    return False


def broadcast_admin_push(
    db: Session,
    *,
    settings: Settings,
    title: str,
    body: str,
    url: str | None = None,
    audience: str = "all",
    respect_cooldown: bool = False,
    tag: str = "antrasha-admin",
) -> dict[str, int]:
    """Ручная рассылка из админки. audience: all | male | female | both."""
    if not web_push_configured(settings):
        return {"eligible": 0, "sent": 0, "failed": 0, "skipped": 0}

    now = datetime.now(timezone.utc)
    cutoff = now - NOTIFY_COOLDOWN
    rows = list(
        db.execute(
            select(PushSubscription).where(PushSubscription.is_active.is_(True))
        ).scalars()
    )

    target_url = (url or "").strip() or f"{settings.public_app_url.rstrip('/')}/"
    if target_url.startswith("/"):
        target_url = f"{settings.public_app_url.rstrip('/')}{target_url}"

    sent = 0
    failed = 0
    skipped = 0
    eligible = 0

    for row in rows:
        if not _audience_matches(row.gender_scope, audience):
            skipped += 1
            continue
        if respect_cooldown and row.last_notified_at is not None:
            last = row.last_notified_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last >= cutoff:
                skipped += 1
                continue

        eligible += 1
        link = target_url if (url or "").strip() else _notification_url_for_scope(
            settings, row.gender_scope
        )
        payload = {
            "title": title.strip(),
            "body": body.strip() or "Новинки — загляните",
            "url": link,
            "tag": tag,
        }
        if _send_one(row, settings=settings, payload=payload):
            row.last_notified_at = now
            sent += 1
        else:
            failed += 1

    db.commit()
    log.info(
        "web_push admin broadcast audience=%s eligible=%s sent=%s failed=%s skipped=%s",
        audience,
        eligible,
        sent,
        failed,
        skipped,
    )
    return {
        "eligible": eligible,
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
    }
