from datetime import datetime, timedelta, timezone

from sqlalchemy import case, exists, func, select
from sqlalchemy.orm import Session

from app.models import Interaction, MarketingCampaign, User, UserSession
from app.services.campaign_links import build_tracking_url

_ENGAGED = exists(
    select(1).where(
        Interaction.session_id == UserSession.id,
    ),
)


def fetch_campaign_dashboard_rows(db: Session) -> list[dict]:
    """Сводка по каждой кампании для дашборда (включая кампании без заходов)."""
    now = datetime.now(timezone.utc)
    since_7d = now - timedelta(days=7)
    since_30d = now - timedelta(days=30)

    engaged_sessions = func.count(
        func.distinct(
            case(
                (_ENGAGED, UserSession.id),
                else_=None,
            ),
        ),
    ).label("engaged_sessions")

    visits = func.count(UserSession.id).label("visits")
    visits_7d = func.count(
        case((UserSession.created_at >= since_7d, UserSession.id), else_=None),
    ).label("visits_7d")
    visits_30d = func.count(
        case((UserSession.created_at >= since_30d, UserSession.id), else_=None),
    ).label("visits_30d")

    session_interactions = func.count(Interaction.id).label("interactions")
    likes = func.count(
        case((Interaction.action == "like", Interaction.id), else_=None),
    ).label("likes")
    dislikes = func.count(
        case((Interaction.action == "dislike", Interaction.id), else_=None),
    ).label("dislikes")

    session_agg = (
        select(
            UserSession.campaign_id.label("campaign_id"),
            visits,
            visits_7d,
            visits_30d,
            engaged_sessions,
            session_interactions,
            likes,
            dislikes,
        )
        .where(UserSession.campaign_id.is_not(None))
        .group_by(UserSession.campaign_id)
        .subquery()
    )

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

    rows = db.execute(
        select(
            MarketingCampaign,
            func.coalesce(session_agg.c.visits, 0),
            func.coalesce(session_agg.c.visits_7d, 0),
            func.coalesce(session_agg.c.visits_30d, 0),
            func.coalesce(session_agg.c.engaged_sessions, 0),
            func.coalesce(session_agg.c.interactions, 0)
            + func.coalesce(user_interactions.c.user_interactions, 0),
            func.coalesce(session_agg.c.likes, 0) + func.coalesce(user_interactions.c.user_likes, 0),
            func.coalesce(session_agg.c.dislikes, 0)
            + func.coalesce(user_interactions.c.user_dislikes, 0),
            func.coalesce(registrations.c.registrations, 0),
        )
        .select_from(MarketingCampaign)
        .outerjoin(session_agg, session_agg.c.campaign_id == MarketingCampaign.id)
        .outerjoin(
            user_interactions,
            user_interactions.c.campaign_id == MarketingCampaign.id,
        )
        .outerjoin(registrations, registrations.c.campaign_id == MarketingCampaign.id)
        .order_by(func.coalesce(session_agg.c.visits, 0).desc(), MarketingCampaign.name),
    ).all()

    out: list[dict] = []
    for row in rows:
        c = row[0]
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
                "interactions": int(row[5]),
                "likes": int(row[6]),
                "dislikes": int(row[7]),
                "registrations": int(row[8]),
            },
        )
    return out


def count_organic_sessions(db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(UserSession)
            .where(UserSession.campaign_id.is_(None)),
        )
        or 0
    )
