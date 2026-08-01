from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.hero_banner import HeroBanner


def list_active_hero_banners(db: Session) -> list[HeroBanner]:
    now = datetime.now(timezone.utc)
    stmt = (
        select(HeroBanner)
        .where(
            HeroBanner.is_active.is_(True),
            or_(HeroBanner.starts_at.is_(None), HeroBanner.starts_at <= now),
            or_(HeroBanner.ends_at.is_(None), HeroBanner.ends_at >= now),
        )
        .order_by(HeroBanner.priority.desc(), HeroBanner.created_at.desc())
    )
    return list(db.scalars(stmt).all())
