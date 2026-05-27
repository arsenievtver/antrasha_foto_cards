from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.promo_banner import PromoBanner, PromoBannerDisplayMode, PromoBannerImpression


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _banner_in_schedule(banner: PromoBanner, now: datetime) -> bool:
    if banner.starts_at and now < banner.starts_at:
        return False
    if banner.ends_at and now > banner.ends_at:
        return False
    return True


def _should_show(banner: PromoBanner, impression: PromoBannerImpression | None) -> bool:
    if not banner.is_active:
        return False
    now = _utcnow()
    if not _banner_in_schedule(banner, now):
        return False
    view_count = impression.view_count if impression else 0
    if banner.display_mode == PromoBannerDisplayMode.every_visit:
        return True
    if banner.display_mode == PromoBannerDisplayMode.once:
        return view_count < 1
    if banner.display_mode == PromoBannerDisplayMode.twice:
        return view_count < 2
    return False


def get_impression(
    db: Session,
    banner_id: uuid.UUID,
    session_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> PromoBannerImpression | None:
    if user_id is not None:
        row = db.scalar(
            select(PromoBannerImpression).where(
                PromoBannerImpression.banner_id == banner_id,
                PromoBannerImpression.user_id == user_id,
            ),
        )
        if row:
            return row
    return db.scalar(
        select(PromoBannerImpression).where(
            PromoBannerImpression.banner_id == banner_id,
            PromoBannerImpression.session_id == session_id,
        ),
    )


def get_or_create_impression(
    db: Session,
    banner_id: uuid.UUID,
    session_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> PromoBannerImpression:
    existing = get_impression(db, banner_id, session_id, user_id)
    if existing:
        if user_id is not None and existing.user_id is None:
            existing.user_id = user_id
        return existing
    row = PromoBannerImpression(
        banner_id=banner_id,
        session_id=session_id,
        user_id=user_id,
        view_count=0,
    )
    db.add(row)
    db.flush()
    return row


def pick_active_banner(
    db: Session,
    session_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> PromoBanner | None:
    banners = db.scalars(
        select(PromoBanner)
        .where(PromoBanner.is_active.is_(True))
        .order_by(PromoBanner.priority.desc(), PromoBanner.created_at.desc()),
    ).all()
    for banner in banners:
        impression = get_impression(db, banner.id, session_id, user_id)
        if _should_show(banner, impression):
            return banner
    return None


def record_banner_seen(
    db: Session,
    banner: PromoBanner,
    session_id: uuid.UUID,
    user_id: uuid.UUID | None,
) -> None:
    if banner.display_mode == PromoBannerDisplayMode.every_visit:
        return
    row = get_or_create_impression(db, banner.id, session_id, user_id)
    row.view_count += 1
    row.last_seen_at = _utcnow()
