from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from app.models import Interaction, MarketingCampaign, User, UserSession
from app.services.campaign_links import build_tracking_url


def _users_have_signup_campaign(db: Session) -> bool:
    try:
        db.execute(select(User.signup_campaign_id).limit(1))
        return True
    except ProgrammingError:
        db.rollback()
        return False


def fetch_campaign_dashboard_rows(db: Session) -> list[dict]:
    """Сводка по каждой кампании для дашборда (включая кампании без заходов)."""
    now = datetime.now(timezone.utc)
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)
    track_registrations = _users_have_signup_campaign(db)

    session_agg = (
        select(
            UserSession.campaign_id.label("campaign_id"),
            func.count(func.distinct(UserSession.id)).label("visits"),
            func.count(
                func.distinct(
                    case(
                        (UserSession.created_at >= since_7d, UserSession.id),
                        else_=None,
                    ),
                ),
            ).label("visits_7d"),
            func.count(
                func.distinct(
                    case(
                        (UserSession.created_at >= since_30d, UserSession.id),
                        else_=None,
                    ),
                ),
            ).label("visits_30d"),
            func.count(
                func.distinct(
                    case(
                        (Interaction.id.isnot(None), UserSession.id),
                        else_=None,
                    ),
                ),
            ).label("engaged_sessions"),
            func.count(Interaction.id).label("session_interactions"),
            func.count(
                case((Interaction.action == "like", Interaction.id), else_=None),
            ).label("likes"),
            func.count(
                case((Interaction.action == "dislike", Interaction.id), else_=None),
            ).label("dislikes"),
        )
        .select_from(UserSession)
        .outerjoin(Interaction, Interaction.session_id == UserSession.id)
        .where(UserSession.campaign_id.is_not(None))
        .group_by(UserSession.campaign_id)
        .subquery()
    )

    user_interactions = None
    registrations = None
    if track_registrations:
        user_interactions = (
            select(
                User.signup_campaign_id.label("campaign_id"),
                func.count(Interaction.id).label("user_interactions"),
                func.count(
                    case((Interaction.action == "like", Interaction.id), else_=None),
                ).label("user_likes"),
                func.count(
                    case((Interaction.action == "dislike", Interaction.id), else_=None),
                ).label("user_dislikes"),
            )
            .select_from(User)
            .join(Interaction, Interaction.user_id == User.id)
            .where(User.signup_campaign_id.is_not(None))
            .group_by(User.signup_campaign_id)
            .subquery()
        )
        registrations = (
            select(
                User.signup_campaign_id.label("campaign_id"),
                func.count(User.id).label("registrations"),
            )
            .where(User.signup_campaign_id.is_not(None))
            .group_by(User.signup_campaign_id)
            .subquery()
        )

    stmt = (
        select(
            MarketingCampaign,
            func.coalesce(session_agg.c.visits, 0),
            func.coalesce(session_agg.c.visits_7d, 0),
            func.coalesce(session_agg.c.visits_30d, 0),
            func.coalesce(session_agg.c.engaged_sessions, 0),
            func.coalesce(session_agg.c.session_interactions, 0),
            func.coalesce(session_agg.c.likes, 0),
            func.coalesce(session_agg.c.dislikes, 0),
        )
        .select_from(MarketingCampaign)
        .outerjoin(session_agg, session_agg.c.campaign_id == MarketingCampaign.id)
    )

    if user_interactions is not None:
        stmt = stmt.add_columns(
            func.coalesce(user_interactions.c.user_interactions, 0),
            func.coalesce(user_interactions.c.user_likes, 0),
            func.coalesce(user_interactions.c.user_dislikes, 0),
            func.coalesce(registrations.c.registrations, 0),
        ).outerjoin(
            user_interactions,
            user_interactions.c.campaign_id == MarketingCampaign.id,
        ).outerjoin(
            registrations,
            registrations.c.campaign_id == MarketingCampaign.id,
        )
    else:
        stmt = stmt.add_columns(
            func.literal(0),
            func.literal(0),
            func.literal(0),
            func.literal(0),
        )

    stmt = stmt.order_by(
        func.coalesce(session_agg.c.visits, 0).desc(),
        MarketingCampaign.name,
    )

    rows = db.execute(stmt).all()

    out: list[dict] = []
    for row in rows:
        c = row[0]
        session_ix = int(row[5])
        session_likes = int(row[6])
        session_dislikes = int(row[7])
        if track_registrations:
            user_ix = int(row[8])
            user_likes = int(row[9])
            user_dislikes = int(row[10])
            registrations_n = int(row[11])
        else:
            user_ix = user_likes = user_dislikes = registrations_n = 0

        out.append(
            {
                "campaign_id": c.id,
                "name": c.name,
                "slug": c.slug,
                "path": c.path,
                "is_active": c.is_active,
                "created_at": c.created_at,
                "tracking_url": build_tracking_url(c),
                "visits": int(row[1]),
                "visits_7d": int(row[2]),
                "visits_30d": int(row[3]),
                "engaged_sessions": int(row[4]),
                "interactions": session_ix + user_ix,
                "likes": session_likes + user_likes,
                "dislikes": session_dislikes + user_dislikes,
                "registrations": registrations_n,
            },
        )
    return out


def count_organic_sessions(db: Session) -> int:
    try:
        return (
            db.scalar(
                select(func.count())
                .select_from(UserSession)
                .where(UserSession.campaign_id.is_(None)),
            )
            or 0
        )
    except ProgrammingError:
        db.rollback()
        return db.scalar(select(func.count()).select_from(UserSession)) or 0


def count_sessions_with_campaign(db: Session) -> int:
    try:
        return (
            db.scalar(
                select(func.count())
                .select_from(UserSession)
                .where(UserSession.campaign_id.is_not(None)),
            )
            or 0
        )
    except ProgrammingError:
        db.rollback()
        return 0
