"""Сводка по пользователям приложения для админки и MCP (только чтение)."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.models import (
    FittingRequest,
    Interaction,
    MarketingCampaign,
    Tag,
    User,
    UserRole,
    UserTagPairWeight,
    UserTagWeight,
)
from app.models.photo import Photo
from app.permissions import effective_worker_permissions
from app.schemas.admin import (
    AdminFittingRequestOut,
    AdminUserDetailOut,
    AdminUserOut,
    AdminUserTagPairWeightStat,
    AdminUserTagWeightStat,
    AdminUserTasteGenderPreview,
    AdminUserTastePhotoOut,
)
from app.services.gift_certificates import (
    active_certificates_for_phone,
    certificate_link,
    phone_lookup_values,
    set_actual_status,
)
from app.services.taste_nearest_photos import taste_previews_for_user
from app.services.web_push import push_account_status_for_user


class AppUserNotFoundError(Exception):
    pass


def user_out(u: User) -> AdminUserOut:
    perms: list[str] = []
    if u.role == UserRole.worker.value:
        perms = effective_worker_permissions(u.admin_permissions)
    return AdminUserOut(
        id=u.id,
        phone=u.phone,
        display_name=u.display_name,
        role=u.role,
        admin_permissions=perms,
        ranking_eval_enabled=bool(u.ranking_eval_enabled),
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )


def signup_campaign_meta(db: Session, u: User) -> dict:
    if not u.signup_campaign_id:
        return {
            "signup_campaign_id": None,
            "signup_campaign_slug": None,
            "signup_campaign_name": None,
        }
    camp = db.get(MarketingCampaign, u.signup_campaign_id)
    if camp is None:
        return {
            "signup_campaign_id": str(u.signup_campaign_id),
            "signup_campaign_slug": None,
            "signup_campaign_name": None,
        }
    return {
        "signup_campaign_id": str(camp.id),
        "signup_campaign_slug": camp.slug,
        "signup_campaign_name": camp.name,
    }


def resolve_user_by_phone(db: Session, phone: str) -> User | None:
    values = phone_lookup_values(phone)
    if not values:
        return None
    return db.scalar(select(User).where(User.phone.in_(values)))


def resolve_user(
    db: Session,
    *,
    user_id: uuid.UUID | None = None,
    phone: str | None = None,
) -> User:
    if user_id is not None:
        u = db.get(User, user_id)
        if u is None:
            raise AppUserNotFoundError("user_id не найден")
        return u
    if phone:
        u = resolve_user_by_phone(db, phone.strip())
        if u is None:
            raise AppUserNotFoundError("пользователь с таким телефоном не найден")
        return u
    raise ValueError("нужен user_id или phone")


def lookup_users_by_phones(db: Session, phones: list[str]) -> dict:
    items: list[dict] = []
    for raw in phones:
        phone = str(raw or "").strip()
        if not phone:
            items.append({"phone": raw, "registered": False, "error": "пустой номер"})
            continue
        user = resolve_user_by_phone(db, phone)
        row = {
            "phone": phone,
            "registered": user is not None,
            "user_id": str(user.id) if user else None,
            "display_name": user.display_name if user else None,
            "role": user.role if user else None,
            "last_login_at": user.last_login_at if user else None,
        }
        items.append(row)
    reg_count = sum(1 for i in items if i.get("registered"))
    return {"registered_count": reg_count, "total": len(items), "items": items}


def _gift_certificates_summary(db: Session, phone: str) -> list[dict]:
    rows: list[dict] = []
    for cert in active_certificates_for_phone(db, phone):
        if set_actual_status(cert):
            db.commit()
            db.refresh(cert)
        rows.append(
            {
                "id": cert.id,
                "code": cert.code,
                "amount": float(cert.amount),
                "nominal": float(cert.nominal) if cert.nominal is not None else None,
                "status": cert.status,
                "public_url": certificate_link(cert.public_slug),
            }
        )
    return rows


def build_admin_user_detail(db: Session, user_id: uuid.UUID) -> AdminUserDetailOut:
    u = db.get(User, user_id)
    if not u:
        raise AppUserNotFoundError("User not found")
    return _build_user_detail(db, u)


def _build_user_detail(db: Session, u: User) -> AdminUserDetailOut:
    uid = u.id
    interactions_total = (
        db.scalar(
            select(func.count()).select_from(Interaction).where(Interaction.user_id == uid),
        )
        or 0
    )
    likes = (
        db.scalar(
            select(func.count()).select_from(Interaction).where(
                Interaction.user_id == uid,
                Interaction.action == "like",
            ),
        )
        or 0
    )
    dislikes = (
        db.scalar(
            select(func.count()).select_from(Interaction).where(
                Interaction.user_id == uid,
                Interaction.action == "dislike",
            ),
        )
        or 0
    )

    interactions_male = (
        db.scalar(
            select(func.count())
            .select_from(Interaction)
            .join(Photo, Photo.id == Interaction.photo_id)
            .where(Interaction.user_id == uid, Photo.gender == "male"),
        )
        or 0
    )
    interactions_female = (
        db.scalar(
            select(func.count())
            .select_from(Interaction)
            .join(Photo, Photo.id == Interaction.photo_id)
            .where(Interaction.user_id == uid, Photo.gender == "female"),
        )
        or 0
    )

    likes_male = (
        db.scalar(
            select(func.count())
            .select_from(Interaction)
            .join(Photo, Photo.id == Interaction.photo_id)
            .where(
                Interaction.user_id == uid,
                Interaction.action == "like",
                Photo.gender == "male",
            ),
        )
        or 0
    )
    likes_female = (
        db.scalar(
            select(func.count())
            .select_from(Interaction)
            .join(Photo, Photo.id == Interaction.photo_id)
            .where(
                Interaction.user_id == uid,
                Interaction.action == "like",
                Photo.gender == "female",
            ),
        )
        or 0
    )

    avg_raw = db.scalar(
        select(func.avg(Interaction.view_time_ms)).where(
            Interaction.user_id == uid,
            Interaction.view_time_ms.isnot(None),
        ),
    )
    avg_view_time_ms = float(avg_raw) if avg_raw is not None else None

    tw_rows = db.execute(
        select(Tag.id, Tag.name, Tag.type, UserTagWeight.weight)
        .join(UserTagWeight, UserTagWeight.tag_id == Tag.id)
        .where(
            UserTagWeight.user_id == uid,
            UserTagWeight.session_id.is_(None),
        ),
    ).all()
    tw_sorted = sorted(tw_rows, key=lambda r: -abs(float(r[3])))

    tag_weights = [
        AdminUserTagWeightStat(
            tag_id=row[0],
            tag_name=row[1],
            tag_type=row[2],
            weight=float(row[3]),
        )
        for row in tw_sorted
    ]

    Tlo = aliased(Tag)
    Thi = aliased(Tag)
    tp_rows = db.execute(
        select(
            UserTagPairWeight.tag_id_lo,
            UserTagPairWeight.tag_id_hi,
            Tlo.name,
            Thi.name,
            UserTagPairWeight.weight,
        )
        .join(Tlo, Tlo.id == UserTagPairWeight.tag_id_lo)
        .join(Thi, Thi.id == UserTagPairWeight.tag_id_hi)
        .where(
            UserTagPairWeight.user_id == uid,
            UserTagPairWeight.session_id.is_(None),
        ),
    ).all()
    tp_sorted = sorted(tp_rows, key=lambda r: -abs(float(r[4])))

    tag_pair_weights = [
        AdminUserTagPairWeightStat(
            tag_a_id=row[0],
            tag_b_id=row[1],
            tag_a_name=row[2],
            tag_b_name=row[3],
            weight=float(row[4]),
        )
        for row in tp_sorted
    ]

    push_active, push_scope = push_account_status_for_user(db, uid)

    taste_previews: list[AdminUserTasteGenderPreview] = []
    taste_updates_total = 0
    any_taste_ready = False
    taste_nearest_legacy: list[AdminUserTastePhotoOut] = []
    for catalog_g, taste_emb, updates, nearest in taste_previews_for_user(db, uid, k=4):
        taste_updates_total += updates
        ready = taste_emb is not None
        any_taste_ready = any_taste_ready or ready
        photos_out = [
            AdminUserTastePhotoOut(
                photo_id=photo.id,
                url=photo.url,
                gender=photo.gender,
                brand=photo.brand,
                cosine=float(cos),
            )
            for photo, cos in nearest
        ]
        if catalog_g == "female" and not taste_nearest_legacy:
            taste_nearest_legacy = photos_out
        taste_previews.append(
            AdminUserTasteGenderPreview(
                collection_gender=catalog_g,
                taste_vector_ready=ready,
                taste_swipe_updates=updates,
                nearest_photos=photos_out,
            )
        )

    return AdminUserDetailOut(
        user=user_out(u),
        interactions_total=interactions_total,
        likes=likes,
        dislikes=dislikes,
        interactions_male=interactions_male,
        interactions_female=interactions_female,
        likes_male=likes_male,
        likes_female=likes_female,
        avg_view_time_ms=avg_view_time_ms,
        tag_weights=tag_weights,
        tag_pair_weights=tag_pair_weights,
        taste_vector_ready=any_taste_ready,
        taste_swipe_updates=taste_updates_total,
        taste_nearest_photos=taste_nearest_legacy,
        taste_previews=taste_previews,
        push_subscribed=push_active,
        push_gender_scope=push_scope,
    )


def user_detail_enriched(db: Session, u: User) -> dict:
    """Профиль как в админке + кампания, активность, заявки, сертификаты."""
    base = _build_user_detail(db, u).model_dump(mode="json")
    uid = u.id
    last_swipe_at = db.scalar(
        select(func.max(Interaction.created_at)).where(Interaction.user_id == uid),
    )
    fitting_by_user = (
        db.scalar(
            select(func.count()).select_from(FittingRequest).where(FittingRequest.user_id == uid),
        )
        or 0
    )
    phone_vals = phone_lookup_values(u.phone) or [u.phone]
    fitting_by_phone = (
        db.scalar(
            select(func.count())
            .select_from(FittingRequest)
            .where(
                FittingRequest.user_id.is_(None),
                FittingRequest.phone.in_(phone_vals),
            ),
        )
        or 0
    )
    now = datetime.now(timezone.utc)
    inactive_days: int | None = None
    if u.last_login_at is None:
        inactive_days = None
    else:
        login = u.last_login_at
        if login.tzinfo is None:
            login = login.replace(tzinfo=timezone.utc)
        inactive_days = max(0, (now - login).days)

    extra = {
        **signup_campaign_meta(db, u),
        "last_swipe_at": last_swipe_at,
        "inactive_days_since_login": inactive_days,
        "fitting_requests_linked": fitting_by_user,
        "fitting_requests_guest_by_phone": fitting_by_phone,
        "active_gift_certificates": _gift_certificates_summary(db, u.phone),
    }
    return {**base, **extra}


def list_app_users(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    role: str | None = None,
    inactive_for_days: int | None = None,
    never_logged_in: bool | None = None,
    registered_from: date | None = None,
    registered_to: date | None = None,
    phone: str | None = None,
    display_name_contains: str | None = None,
) -> dict:
    filters = []
    if role:
        filters.append(User.role == role)
    if never_logged_in:
        filters.append(User.last_login_at.is_(None))
    if inactive_for_days is not None and inactive_for_days >= 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=inactive_for_days)
        filters.append(or_(User.last_login_at.is_(None), User.last_login_at < cutoff))
    if registered_from is not None:
        filters.append(func.date(User.created_at) >= registered_from)
    if registered_to is not None:
        filters.append(func.date(User.created_at) <= registered_to)
    if phone:
        values = phone_lookup_values(phone.strip())
        if not values:
            return {"total": 0, "skip": skip, "limit": limit, "items": []}
        filters.append(User.phone.in_(values))
    if display_name_contains:
        q = display_name_contains.strip()
        if q:
            filters.append(User.display_name.ilike(f"%{q}%"))

    count_q = select(func.count()).select_from(User)
    list_q = select(User).order_by(User.created_at.desc())
    if filters:
        count_q = count_q.where(*filters)
        list_q = list_q.where(*filters)
    total = db.scalar(count_q) or 0
    rows = db.scalars(list_q.offset(skip).limit(limit)).all()
    items: list[dict] = []
    for u in rows:
        row = user_out(u).model_dump(mode="json")
        row.update(signup_campaign_meta(db, u))
        if u.last_login_at is None:
            row["inactive_days_since_login"] = None
        else:
            login = u.last_login_at
            if login.tzinfo is None:
                login = login.replace(tzinfo=timezone.utc)
            row["inactive_days_since_login"] = max(
                0, (datetime.now(timezone.utc) - login).days
            )
        items.append(row)
    return {"total": total, "skip": skip, "limit": limit, "items": items}


def list_fitting_requests_filtered(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 50,
    user_id: uuid.UUID | None = None,
    phone: str | None = None,
    status: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
) -> dict:
    filters = []
    if user_id is not None:
        filters.append(FittingRequest.user_id == user_id)
    if phone:
        values = phone_lookup_values(phone.strip())
        if values:
            filters.append(FittingRequest.phone.in_(values))
        else:
            return {"total": 0, "skip": skip, "limit": limit, "items": []}
    if status:
        filters.append(FittingRequest.status == status.strip())
    if created_from is not None:
        filters.append(func.date(FittingRequest.created_at) >= created_from)
    if created_to is not None:
        filters.append(func.date(FittingRequest.created_at) <= created_to)

    count_q = select(func.count()).select_from(FittingRequest)
    list_q = (
        select(FittingRequest)
        .order_by(FittingRequest.created_at.desc())
        .options(selectinload(FittingRequest.liked_photos))
    )
    if filters:
        count_q = count_q.where(*filters)
        list_q = list_q.where(*filters)
    total = db.scalar(count_q) or 0
    rows = db.scalars(list_q.offset(skip).limit(limit)).all()
    items = [
        AdminFittingRequestOut(
            id=row.id,
            user_id=row.user_id,
            display_name=row.display_name,
            phone=row.phone,
            likes=row.likes,
            total=row.total,
            match_rate=float(row.match_rate or 0),
            note=row.note,
            status=row.status,
            created_at=row.created_at,
            liked_photos=[x.photo_url for x in row.liked_photos],
        ).model_dump(mode="json")
        for row in rows
    ]
    return {"total": total, "skip": skip, "limit": limit, "items": items}
