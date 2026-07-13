import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError, ProgrammingError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased, selectinload
from starlette.responses import Response

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, get_admin_principal, require_superuser
from app.models import (
    PHOTO_SOURCE_YC_OBJECT_STORAGE,
    Brand,
    FeedSettings,
    FittingRequest,
    Interaction,
    MarketingCampaign,
    Photo,
    PhotoTag,
    Tag,
    TagGroup,
    User,
    UserRole,
    UserSession,
    UserTagPairWeight,
    UserTagWeight,
)
from app.models.marketing_campaign import normalize_campaign_slug
from app.schemas.admin import (
    AdminCatalogGroupOut,
    AdminCatalogSectionOut,
    AdminCatalogSubgroupOut,
    AdminCatalogTagOut,
    AdminPhotoBulkDeleteItem,
    AdminPhotoListResponse,
    AdminPhotoOut,
    AdminPhotosBulkDeleteBody,
    AdminPhotosBulkDeleteResponse,
    AdminPhotoTagOut,
    AdminPhotoTagsPutBody,
    AdminBrandCreateRequest,
    FeedSettingsOut,
    FeedSettingsPatch,
    AdminFittingRequestListResponse,
    AdminFittingRequestOut,
    AdminBrandListResponse,
    AdminBrandOut,
    AdminAttributionDebugOut,
    AdminAttributionDebugSession,
    AdminCampaignCreateRequest,
    AdminCampaignListResponse,
    AdminCampaignOut,
    AdminCampaignVisitStat,
    AdminStatsOut,
    AdminTagCatalogResponse,
    AdminTagCreateRequest,
    AdminTagGroupCreateRequest,
    AdminTagGroupListResponse,
    AdminTagGroupOut,
    AdminTagGroupUpdateRequest,
    AdminTagListResponse,
    AdminTagOut,
    AdminTagUpdateRequest,
    AdminUserCreateRequest,
    AdminUserDetailOut,
    AdminUserListResponse,
    AdminUserOut,
    AdminUserTagPairWeightStat,
    AdminUserTagWeightStat,
    AdminUserUpdateRequest,
    AdminWorkerTagCreateBody,
    assert_pin_for_role,
)
from app.security import hash_pin
from app.services.campaign_links import build_tracking_url, normalize_campaign_path
from app.services.campaign_stats import (
    count_organic_sessions,
    count_sessions_with_campaign,
    fetch_campaign_dashboard_rows,
)
from app.services.tagging_validation import validate_catalog_tag_selection
from app.services.yc_photo_sync import run_sync_job_commit
from app.services.yc_storage import bulk_delete_photo_files_from_object_storage

TAGGING_CLAIM_TTL = timedelta(minutes=5)

_CATALOG_SKIP_GROUP_SLUGS = frozenset({"legacy", "garment_gender"})

SUBGROUP_LABELS = {
    "palette": "Основная палитра",
    "tone": "Доп. оттенок",
}

log = logging.getLogger("app.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"])


def _pin_validation_http(role: str, pin: str) -> None:
    try:
        assert_pin_for_role(role, pin)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


def _photo_out(p: Photo, *, viewer_user_id: uuid.UUID | None = None) -> AdminPhotoOut:
    tags = []
    for pt in p.photo_tags:
        gslug = None
        if pt.tag.group:
            gslug = pt.tag.group.slug
        tags.append(
            AdminPhotoTagOut(
                tag_id=pt.tag_id,
                name=pt.tag.name,
                type=pt.tag.type,
                weight=float(pt.weight),
                group_slug=gslug,
            ),
        )
    now = datetime.now(timezone.utc)
    claim_expires_at = None
    claim_is_mine = False
    if (
        p.tagging_claimed_until is not None
        and p.tagging_claimed_until > now
        and p.tagging_claimed_by_id is not None
    ):
        claim_expires_at = p.tagging_claimed_until
        if viewer_user_id is not None and p.tagging_claimed_by_id == viewer_user_id:
            claim_is_mine = True
    return AdminPhotoOut(
        id=p.id,
        url=p.url,
        gender=p.gender,
        is_active=p.is_active,
        created_at=p.created_at,
        tags=tags,
        tagging_uncertain=p.tagging_uncertain,
        tagging_review_done=p.tagging_review_done,
        worker_signal_love=p.worker_signal_love,
        worker_signal_hit=p.worker_signal_hit,
        worker_signal_hard=p.worker_signal_hard,
        brand_id=p.brand_id,
        brand=p.brand,
        price_segment=p.price_segment,
        moy_sklad_id=p.moy_sklad_id,
        tags_version=p.tags_version,
        claim_expires_at=claim_expires_at,
        claim_is_mine=claim_is_mine,
        likes_count=p.likes_count,
        dislikes_count=p.dislikes_count,
    )


def _expire_stale_tagging_claims(db: Session) -> None:
    now = datetime.now(timezone.utc)
    db.execute(
        update(Photo)
        .where(
            Photo.tagging_claimed_until.is_not(None),
            Photo.tagging_claimed_until < now,
        )
        .values(tagging_claimed_by_id=None, tagging_claimed_until=None),
    )


def _tagging_queue_pending_clause():
    """Очередь: фото ещё не прошли полную разметку (tagging_review_done)."""
    return Photo.tagging_review_done.is_(False)


def _tag_catalog_selectinloads():
    return (
        selectinload(Photo.photo_tags)
        .selectinload(PhotoTag.tag)
        .selectinload(Tag.group)
    )


def _catalog_group_out(g: TagGroup, tglist: list[Tag]) -> AdminCatalogGroupOut:
    def subgroup_sort_key(sk: str | None) -> tuple:
        order = {None: 0, "palette": 1, "tone": 2}
        return (order.get(sk, 50), sk or "")

    sub_map: dict[str | None, list[Tag]] = {}
    for t in tglist:
        sub_map.setdefault(t.subgroup_key, []).append(t)
    subgroups_out: list[AdminCatalogSubgroupOut] = []
    for sk in sorted(sub_map.keys(), key=subgroup_sort_key):
        label = "Теги" if sk is None else SUBGROUP_LABELS.get(sk, sk)
        subgroups_out.append(
            AdminCatalogSubgroupOut(
                key=sk,
                label=label,
                tags=[
                    AdminCatalogTagOut(
                        id=t.id,
                        name=t.name,
                        subgroup_key=t.subgroup_key,
                        sort_order=t.sort_order,
                        recommendation_weight=t.recommendation_weight,
                    )
                    for t in sub_map[sk]
                ],
            ),
        )
    if not subgroups_out:
        subgroups_out.append(AdminCatalogSubgroupOut(key=None, label="Теги", tags=[]))
    return AdminCatalogGroupOut(
        id=g.id,
        slug=g.slug,
        title=g.title,
        min_tags=g.min_tags,
        max_tags=g.max_tags,
        swipe_tier=g.swipe_tier,
        subgroups=subgroups_out,
    )


def _tag_group_out(g: TagGroup) -> AdminTagGroupOut:
    return AdminTagGroupOut(
        id=g.id,
        slug=g.slug,
        title=g.title,
        min_tags=g.min_tags,
        max_tags=g.max_tags,
        swipe_tier=g.swipe_tier,
        group_sort=g.group_sort,
    )


def build_tag_catalog(db: Session) -> AdminTagCatalogResponse:
    groups = db.scalars(
        select(TagGroup)
        .where(TagGroup.slug.not_in(_CATALOG_SKIP_GROUP_SLUGS))
        .order_by(TagGroup.group_sort, TagGroup.title),
    ).all()
    if not groups:
        return AdminTagCatalogResponse(groups=[], sections=[])
    gids = [g.id for g in groups]
    tag_rows = db.scalars(
        select(Tag).where(Tag.group_id.in_(gids)).order_by(Tag.sort_order, Tag.name),
    ).all()
    by_gid: dict[uuid.UUID, list[Tag]] = {}
    for t in tag_rows:
        by_gid.setdefault(t.group_id, []).append(t)

    groups_out = [_catalog_group_out(g, by_gid.get(g.id, [])) for g in groups]
    return AdminTagCatalogResponse(groups=groups_out, sections=[])


def _viewer_id(principal: AdminPrincipal) -> uuid.UUID | None:
    return principal.user.id if principal.user else None


def _campaign_visit_rows(db: Session) -> list[tuple[uuid.UUID, str, str, int]]:
    return list(
        db.execute(
            select(
                MarketingCampaign.id,
                MarketingCampaign.name,
                MarketingCampaign.slug,
                func.count(UserSession.id),
            )
            .outerjoin(UserSession, UserSession.campaign_id == MarketingCampaign.id)
            .group_by(
                MarketingCampaign.id,
                MarketingCampaign.name,
                MarketingCampaign.slug,
            )
            .order_by(func.count(UserSession.id).desc(), MarketingCampaign.name),
        ).all(),
    )


def _campaign_out(c: MarketingCampaign, *, visits: int) -> AdminCampaignOut:
    return AdminCampaignOut(
        id=c.id,
        name=c.name,
        slug=c.slug,
        path=c.path,
        is_active=c.is_active,
        created_at=c.created_at,
        tracking_url=build_tracking_url(c),
        visits=visits,
    )


@router.get("/stats", response_model=AdminStatsOut)
def admin_stats(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminStatsOut:
    users = db.scalar(select(func.count()).select_from(User)) or 0
    workers = (
        db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.worker.value),
        )
        or 0
    )
    yc = Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE
    photos = db.scalar(select(func.count()).select_from(Photo).where(yc)) or 0
    active_photos = (
        db.scalar(
            select(func.count()).select_from(Photo).where(yc, Photo.is_active.is_(True)),
        )
        or 0
    )
    tags = db.scalar(select(func.count()).select_from(Tag)) or 0
    interactions = db.scalar(select(func.count()).select_from(Interaction)) or 0
    photos_male = (
        db.scalar(
            select(func.count())
            .select_from(Photo)
            .where(yc, func.lower(Photo.gender) == "male"),
        )
        or 0
    )
    photos_female = (
        db.scalar(
            select(func.count())
            .select_from(Photo)
            .where(yc, func.lower(Photo.gender) == "female"),
        )
        or 0
    )
    sessions_total = db.scalar(select(func.count()).select_from(UserSession)) or 0
    sessions_with_campaign = count_sessions_with_campaign(db)
    attributed_total = sessions_with_campaign or 0
    try:
        campaign_rows = fetch_campaign_dashboard_rows(db)
    except ProgrammingError:
        db.rollback()
        log.exception("admin_stats: campaign breakdown unavailable (run alembic upgrade head?)")
        campaign_rows = []
    campaign_visits = []
    for row in campaign_rows:
        v = row["visits"]
        engaged = row["engaged_sessions"]
        campaign_visits.append(
            AdminCampaignVisitStat(
                campaign_id=row["campaign_id"],
                name=row["name"],
                slug=row["slug"],
                path=row["path"],
                is_active=row["is_active"],
                tracking_url=row["tracking_url"],
                visits=v,
                visits_7d=row["visits_7d"],
                visits_30d=row["visits_30d"],
                engaged_sessions=engaged,
                engagement_rate=round(100.0 * engaged / v, 1) if v else 0.0,
                interactions=row["interactions"],
                likes=row["likes"],
                dislikes=row["dislikes"],
                registrations=row["registrations"],
                visit_share=round(100.0 * v / attributed_total, 1) if attributed_total else 0.0,
            ),
        )
    sessions_organic = count_organic_sessions(db)
    return AdminStatsOut(
        users=users,
        workers=workers,
        photos=photos,
        active_photos=active_photos,
        tags=tags,
        interactions=interactions,
        photos_male=photos_male,
        photos_female=photos_female,
        sessions_total=sessions_total,
        sessions_with_campaign=sessions_with_campaign,
        sessions_organic=sessions_organic,
        public_app_url=settings.public_app_url.rstrip("/"),
        campaign_visits=campaign_visits,
    )


@router.get("/feed-settings", response_model=FeedSettingsOut)
def get_feed_settings(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> FeedSettingsOut:
    row = db.get(FeedSettings, 1)
    if row is None:
        return FeedSettingsOut(require_tagging_review_for_feed=False)
    return FeedSettingsOut(require_tagging_review_for_feed=row.require_tagging_review_for_feed)


@router.patch("/feed-settings", response_model=FeedSettingsOut)
def patch_feed_settings(
    body: FeedSettingsPatch,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> FeedSettingsOut:
    _ = _su
    row = db.get(FeedSettings, 1)
    if row is None:
        row = FeedSettings(
            id=1,
            require_tagging_review_for_feed=body.require_tagging_review_for_feed,
        )
        db.add(row)
    else:
        row.require_tagging_review_for_feed = body.require_tagging_review_for_feed
    db.commit()
    db.refresh(row)
    return FeedSettingsOut(require_tagging_review_for_feed=row.require_tagging_review_for_feed)


# Поддерживаемые сортировки в /admin/photos. Значения сохраняйте синхронно с фронтом (admin/src/pages/Photos.jsx).
ADMIN_PHOTOS_SORTS = {
    "recent",          # по умолчанию: новые сверху
    "top_likes",       # больше лайков
    "top_dislikes",    # больше дизлайков
    "top_rating",      # выше рейтинг (likes - dislikes)
    "bottom_rating",   # ниже рейтинг (антирейтинг)
}


def _photos_order_by(sort: str):
    rating = (Photo.likes_count - Photo.dislikes_count).label("rating")
    if sort == "top_likes":
        return [Photo.likes_count.desc(), Photo.created_at.desc()]
    if sort == "top_dislikes":
        return [Photo.dislikes_count.desc(), Photo.created_at.desc()]
    if sort == "top_rating":
        return [rating.desc(), Photo.created_at.desc()]
    if sort == "bottom_rating":
        return [rating.asc(), Photo.created_at.desc()]
    return [Photo.created_at.desc()]


@router.get("/photos", response_model=AdminPhotoListResponse)
def list_photos(
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    gender: str | None = Query(None, description="male | female"),
    active_only: bool = Query(False),
    tagging_done_only: bool = Query(False, description="только завершённая разметка"),
    brand_id: uuid.UUID | None = Query(None, description="фильтр по бренду"),
    no_reactions_only: bool = Query(
        False,
        description="только без лайков и дизлайков (likes_count=0 и dislikes_count=0)",
    ),
    sort: str = Query(
        "recent",
        description="recent | top_likes | top_dislikes | top_rating | bottom_rating",
    ),
) -> AdminPhotoListResponse:
    _expire_stale_tagging_claims(db)
    db.flush()
    if sort not in ADMIN_PHOTOS_SORTS:
        sort = "recent"
    cond = [Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE]
    if gender:
        cond.append(func.lower(Photo.gender) == gender.strip().lower())
    if active_only:
        cond.append(Photo.is_active.is_(True))
    if tagging_done_only:
        cond.append(Photo.tagging_review_done.is_(True))
    if brand_id is not None:
        cond.append(Photo.brand_id == brand_id)
    if no_reactions_only:
        cond.append(Photo.likes_count == 0)
        cond.append(Photo.dislikes_count == 0)
    count_q = select(func.count()).select_from(Photo)
    if cond:
        count_q = count_q.where(*cond)
    total = db.scalar(count_q) or 0
    q = select(Photo)
    if cond:
        q = q.where(*cond)
    q = (
        q.order_by(*_photos_order_by(sort))
        .offset(skip)
        .limit(limit)
        .options(_tag_catalog_selectinloads())
    )
    rows = db.scalars(q).unique().all()
    vid = _viewer_id(principal)
    return AdminPhotoListResponse(
        items=[_photo_out(p, viewer_user_id=vid) for p in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/photos/{photo_id}", response_model=AdminPhotoOut)
def get_admin_photo(
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPhotoOut:
    """Одно фото — для обновления карточки после конфликта версии и т.п."""
    _expire_stale_tagging_claims(db)
    db.flush()
    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo_id, Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return _photo_out(photo, viewer_user_id=_viewer_id(principal))


@router.post("/photos/sync-object-storage")
def sync_photos_from_object_storage(
    purge: bool = Query(
        False,
        description=(
            "Если True — фотки, которых уже нет в бакете, удаляются из БД полностью "
            "(каскадно зачищаются связанные теги/интеракции). По умолчанию False: "
            "такие фотки только деактивируются (is_active=False)."
        ),
    ),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> dict:
    _ = _principal
    if not settings.yc_s3_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Yandex S3 ключи не настроены",
        )
    return run_sync_job_commit(
        settings,
        deactivate_not_in_bucket=True,
        purge_not_in_bucket=purge,
    )


@router.get("/tagging-queue", response_model=AdminPhotoListResponse)
def list_tagging_queue(
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
) -> AdminPhotoListResponse:
    """Фото с неполной разметкой (число тегов ≤ лимита). У сотрудников скрыты чужие брони."""
    _expire_stale_tagging_claims(db)
    db.flush()
    now = datetime.now(timezone.utc)
    cond = [
        Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
        Photo.is_active.is_(True),
        _tagging_queue_pending_clause(),
    ]
    if principal.role == "worker":
        assert principal.user is not None
        wid = principal.user.id
        cond.append(
            or_(
                Photo.tagging_claimed_until.is_(None),
                Photo.tagging_claimed_until < now,
                Photo.tagging_claimed_by_id == wid,
            ),
        )
    count_q = select(func.count()).select_from(Photo).where(*cond)
    total = db.scalar(count_q) or 0
    q = (
        select(Photo)
        .where(*cond)
        .order_by(Photo.created_at.asc())
        .offset(skip)
        .limit(limit)
        .options(_tag_catalog_selectinloads())
    )
    rows = db.scalars(q).unique().all()
    vid = _viewer_id(principal)
    return AdminPhotoListResponse(
        items=[_photo_out(p, viewer_user_id=vid) for p in rows],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/tagging-queue/acquire-next", response_model=AdminPhotoOut)
def acquire_next_tagging_photo(
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPhotoOut:
    """Атомарно выдаёт следующее фото без тегов и ставит бронь (только сотрудник)."""
    _expire_stale_tagging_claims(db)
    db.flush()
    now = datetime.now(timezone.utc)

    if principal.role == "superuser":
        photo = db.execute(
            select(Photo)
            .where(
                Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
                Photo.is_active.is_(True),
                _tagging_queue_pending_clause(),
            )
            .order_by(Photo.created_at.asc())
            .limit(1)
            .options(_tag_catalog_selectinloads()),
        ).scalar_one_or_none()
        if not photo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Нет фото в очереди разметки",
            )
        return _photo_out(photo)

    if principal.role != "worker" or principal.user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только для сотрудников",
        )
    wid = principal.user.id
    claim_ok = or_(
        Photo.tagging_claimed_until.is_(None),
        Photo.tagging_claimed_until < now,
        Photo.tagging_claimed_by_id == wid,
    )
    photo = db.execute(
        select(Photo)
        .where(
            Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
            Photo.is_active.is_(True),
            _tagging_queue_pending_clause(),
            claim_ok,
        )
        .order_by(Photo.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one_or_none()
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Нет доступных фото в очереди (попробуйте позже)",
        )
    photo.tagging_claimed_by_id = wid
    photo.tagging_claimed_until = now + TAGGING_CLAIM_TTL
    db.commit()
    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo.id)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one()
    return _photo_out(photo, viewer_user_id=wid)


@router.post("/tagging-queue/{photo_id}/claim", response_model=AdminPhotoOut)
def claim_tagging_photo(
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPhotoOut:
    """Забронировать конкретное фото из списка (сотрудник)."""
    if principal.role != "worker" or principal.user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Бронирование доступно только сотрудникам",
        )
    _expire_stale_tagging_claims(db)
    db.flush()
    now = datetime.now(timezone.utc)
    wid = principal.user.id

    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo_id)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one_or_none()
    if not photo or photo.source_type != PHOTO_SOURCE_YC_OBJECT_STORAGE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    if photo.tagging_review_done:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Разметка этого фото уже завершена",
        )
    if not photo.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Фото неактивно — не из очереди разметки",
        )

    active_claim = (
        photo.tagging_claimed_until is not None
        and photo.tagging_claimed_until > now
        and photo.tagging_claimed_by_id is not None
        and photo.tagging_claimed_by_id != wid
    )
    if active_claim:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Фото занято другим сотрудником",
        )

    photo.tagging_claimed_by_id = wid
    photo.tagging_claimed_until = now + TAGGING_CLAIM_TTL
    db.commit()
    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo_id)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one()
    return _photo_out(photo, viewer_user_id=wid)


@router.post("/tagging-queue/{photo_id}/release", status_code=status.HTTP_204_NO_CONTENT)
def release_tagging_photo(
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> None:
    """Снять свою бронь без сохранения тегов."""
    if principal.role != "worker" or principal.user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для сотрудников")
    photo = db.get(Photo, photo_id)
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    if photo.tagging_claimed_by_id != principal.user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Это не ваша бронь")
    photo.tagging_claimed_by_id = None
    photo.tagging_claimed_until = None
    db.commit()


@router.post("/photos/bulk-delete", response_model=AdminPhotosBulkDeleteResponse)
def bulk_delete_photos(
    body: AdminPhotosBulkDeleteBody,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPhotosBulkDeleteResponse:
    """
    Пакетное удаление фото: один S3 `delete_objects` на бакет + удаления в БД.

    Запись в БД удаляется всегда (если фото найдено), даже если S3 вернул ошибку —
    иначе админка показывает HTTP 200, но список не меняется. Ошибки стораджа
    логируются и возвращаются в `detail` при `ok: true`.

    Старая реализация делала отдельный `boto3.session` + `delete_object` на каждое
    фото и отдельный `db.commit()` — на 50+ фото это выходило за 60 c nginx
    `proxy_read_timeout`, фронт получал 504, хотя бэкенд продолжал удалять.
    """
    # Сохраняем порядок и убираем дубликаты (на случай повторов в теле запроса).
    photo_ids: list[uuid.UUID] = list(dict.fromkeys(body.photo_ids))

    photos_by_id: dict[uuid.UUID, Photo] = {
        p.id: p
        for p in db.scalars(select(Photo).where(Photo.id.in_(photo_ids))).all()
    }

    # url → ошибка S3 (или None при успехе / неприменимо). Один S3-клиент на весь батч.
    urls = [photos_by_id[pid].url for pid in photo_ids if pid in photos_by_id]
    storage_errors_by_url = bulk_delete_photo_files_from_object_storage(settings, urls)

    results: list[AdminPhotoBulkDeleteItem] = []
    for pid in photo_ids:
        photo = photos_by_id.get(pid)
        if not photo:
            results.append(AdminPhotoBulkDeleteItem(id=pid, ok=False, detail="not_found"))
            continue
        s_err = storage_errors_by_url.get(photo.url)
        if s_err:
            log.warning(
                "bulk_delete photo_id=%s storage failed (DB row will still be removed): %s",
                pid,
                s_err,
            )
        try:
            db.delete(photo)
            db.commit()
            detail = f"object_storage: {s_err}" if s_err else None
            results.append(AdminPhotoBulkDeleteItem(id=pid, ok=True, detail=detail))
        except Exception as e:
            db.rollback()
            log.exception("bulk_delete photo_id=%s db failed", pid)
            results.append(AdminPhotoBulkDeleteItem(id=pid, ok=False, detail=str(e)))
    return AdminPhotosBulkDeleteResponse(results=results)


@router.put("/photos/{photo_id}/tags", response_model=AdminPhotoOut)
def put_photo_tags(
    photo_id: uuid.UUID,
    body: AdminPhotoTagsPutBody,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminPhotoOut:
    _expire_stale_tagging_claims(db)
    db.flush()
    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo_id)
        .options(_tag_catalog_selectinloads())
        .with_for_update(),
    ).scalar_one_or_none()
    if not photo or photo.source_type != PHOTO_SOURCE_YC_OBJECT_STORAGE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    if body.expected_tags_version is not None and photo.tags_version != body.expected_tags_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Фото уже изменено (теги или разметка). Обновите данные и попробуйте сохранить снова.",
        )

    tag_ids = [a.tag_id for a in body.tags]
    if len(tag_ids) != len(set(tag_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate tag_id in list",
        )
    if tag_ids:
        found = db.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all()
        if len(found) != len(set(tag_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown tag_id in list",
            )

    verrors = validate_catalog_tag_selection(db, tag_ids)
    if verrors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=" ".join(verrors),
        )

    photo.tagging_uncertain = False
    photo.worker_signal_love = body.worker_signal_love
    photo.worker_signal_hit = body.worker_signal_hit
    photo.worker_signal_hard = body.worker_signal_hard
    photo.tagging_review_done = True

    if body.apply_brand:
        if body.brand_id is not None:
            br = db.get(Brand, body.brand_id)
            if not br:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="brand_id: бренд не найден",
                )
            photo.brand_id = body.brand_id
            photo.brand = br.name
        else:
            photo.brand_id = None
            photo.brand = None

    _body_patch = body.model_dump(exclude_unset=True)
    if "moy_sklad_id" in _body_patch:
        raw = _body_patch.get("moy_sklad_id")
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            photo.moy_sklad_id = None
        else:
            s = raw.strip() if isinstance(raw, str) else str(raw)
            photo.moy_sklad_id = s[:128] if s else None

    for pt in list(photo.photo_tags):
        db.delete(pt)
    db.flush()
    for assign in body.tags:
        db.add(
            PhotoTag(photo_id=photo.id, tag_id=assign.tag_id, weight=assign.weight),
        )
    if principal.role == "worker" and principal.user:
        if photo.tagging_claimed_by_id == principal.user.id:
            photo.tagging_claimed_by_id = None
            photo.tagging_claimed_until = None
    photo.tags_version = photo.tags_version + 1
    db.commit()
    photo = db.execute(
        select(Photo)
        .where(Photo.id == photo_id)
        .options(_tag_catalog_selectinloads()),
    ).scalar_one()
    return _photo_out(photo, viewer_user_id=_viewer_id(principal))


@router.get("/tag-groups", response_model=AdminTagGroupListResponse)
def list_tag_groups(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagGroupListResponse:
    rows = db.scalars(
        select(TagGroup)
        .where(TagGroup.slug.not_in(_CATALOG_SKIP_GROUP_SLUGS))
        .order_by(TagGroup.group_sort, TagGroup.title),
    ).all()
    return AdminTagGroupListResponse(items=[_tag_group_out(g) for g in rows])


@router.post("/tag-groups", response_model=AdminTagGroupOut, status_code=status.HTTP_201_CREATED)
def create_tag_group(
    body: AdminTagGroupCreateRequest,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagGroupOut:
    slug = body.slug.strip().lower().replace(" ", "_")
    if slug in _CATALOG_SKIP_GROUP_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Такой slug зарезервирован",
        )
    if db.scalar(select(TagGroup.id).where(TagGroup.slug == slug)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Группа с таким slug уже есть",
        )
    mx = db.scalar(select(func.coalesce(func.max(TagGroup.group_sort), -1)))
    sort_order = int(mx) + 1 if mx is not None else 0
    g = TagGroup(
        slug=slug,
        title=body.title.strip(),
        section="catalog",
        section_sort=0,
        group_sort=sort_order,
        min_tags=body.min_tags,
        max_tags=body.max_tags,
        swipe_tier="strong",
    )
    db.add(g)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось создать группу",
        ) from None
    db.refresh(g)
    return _tag_group_out(g)


@router.patch("/tag-groups/{group_id}", response_model=AdminTagGroupOut)
def update_tag_group(
    group_id: uuid.UUID,
    body: AdminTagGroupUpdateRequest,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagGroupOut:
    g = db.get(TagGroup, group_id)
    if not g or g.slug in _CATALOG_SKIP_GROUP_SLUGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    if body.title is not None:
        g.title = body.title.strip()
    if body.min_tags is not None:
        g.min_tags = body.min_tags
    if body.max_tags is not None:
        g.max_tags = body.max_tags
    if body.group_sort is not None:
        g.group_sort = body.group_sort
    db.commit()
    db.refresh(g)
    return _tag_group_out(g)


@router.delete("/tag-groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag_group(
    group_id: uuid.UUID,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> Response:
    g = db.get(TagGroup, group_id)
    if not g or g.slug in _CATALOG_SKIP_GROUP_SLUGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    try:
        db.execute(delete(Tag).where(Tag.group_id == group_id))
        result = db.execute(delete(TagGroup).where(TagGroup.id == group_id))
        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        log.warning("delete_tag_group integrity_error group_id=%s", group_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить группу: остались связанные записи.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        log.exception("delete_tag_group failed group_id=%s", group_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка базы при удалении группы.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tag/catalog", response_model=AdminTagCatalogResponse)
def get_tag_catalog(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagCatalogResponse:
    return build_tag_catalog(db)


@router.post("/tag-groups/{group_id}/tags", response_model=AdminCatalogTagOut)
def create_tag_in_group(
    group_id: uuid.UUID,
    body: AdminWorkerTagCreateBody,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminCatalogTagOut:
    """Добавить тег в группу (виден всем сотрудникам)."""
    g = db.get(TagGroup, group_id)
    if not g or g.slug in _CATALOG_SKIP_GROUP_SLUGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    name = body.name.strip()
    exists = db.scalar(select(Tag.id).where(Tag.group_id == g.id, Tag.name == name))
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Такой тег уже есть в группе",
        )
    mx = db.scalar(select(func.coalesce(func.max(Tag.sort_order), -1)).where(Tag.group_id == g.id))
    sort_order = int(mx) + 1 if mx is not None else 0
    uid = principal.user.id if principal.user else None
    t = Tag(
        name=name,
        type=g.slug,
        group_id=g.id,
        subgroup_key=None,
        sort_order=sort_order,
        recommendation_weight=55,
        created_by_user_id=uid,
    )
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не удалось сохранить тег",
        ) from None
    db.refresh(t)
    return AdminCatalogTagOut(
        id=t.id,
        name=t.name,
        subgroup_key=t.subgroup_key,
        sort_order=t.sort_order,
        recommendation_weight=t.recommendation_weight,
    )


@router.get("/tags", response_model=AdminTagListResponse)
def list_tags(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagListResponse:
    rows = db.scalars(
        select(Tag)
        .join(TagGroup, Tag.group_id == TagGroup.id)
        .where(TagGroup.slug.not_in(_CATALOG_SKIP_GROUP_SLUGS))
        .options(selectinload(Tag.group))
        .order_by(TagGroup.group_sort, TagGroup.title, Tag.name),
    ).all()
    items = []
    for t in rows:
        g = t.group
        items.append(
            AdminTagOut(
                id=t.id,
                name=t.name,
                type=t.type,
                group_id=t.group_id,
                group_slug=g.slug if g else None,
                group_title=g.title if g else None,
            ),
        )
    return AdminTagListResponse(items=items)


@router.post("/tags", response_model=AdminTagOut)
def create_tag(
    body: AdminTagCreateRequest,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagOut:
    name = body.name.strip()
    g: TagGroup | None = None
    if body.group_id:
        g = db.get(TagGroup, body.group_id)
    type_slug = (body.type or "").strip()
    if g is None and type_slug:
        g = db.scalar(select(TagGroup).where(TagGroup.slug == type_slug))
    if g is None or g.slug in _CATALOG_SKIP_GROUP_SLUGS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Выберите группу (group_id) из списка категорий",
        )
    mx = db.scalar(select(func.coalesce(func.max(Tag.sort_order), -1)).where(Tag.group_id == g.id))
    sort_order = int(mx) + 1 if mx is not None else 0
    t = Tag(
        name=name,
        type=g.slug,
        group_id=g.id,
        subgroup_key=None,
        sort_order=sort_order,
        recommendation_weight=55,
        created_by_user_id=None,
    )
    db.add(t)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Тег с таким именем уже есть в этой группе",
        ) from None
    db.refresh(t)
    return AdminTagOut(
        id=t.id,
        name=t.name,
        type=t.type,
        group_id=t.group_id,
        group_slug=g.slug,
        group_title=g.title,
    )


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: uuid.UUID,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> Response:
    """SQL DELETE: ORM session.delete(tag) даёт 500 — пытается обнулить photo_tags.tag_id (NOT NULL)."""
    try:
        result = db.execute(delete(Tag).where(Tag.id == tag_id))
        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        log.warning("delete_tag integrity_error tag_id=%s", tag_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить тег: в БД остались связанные записи.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        log.exception("delete_tag failed tag_id=%s", tag_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка базы при удалении тега.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/tags/{tag_id}", response_model=AdminTagOut)
def update_tag(
    tag_id: uuid.UUID,
    body: AdminTagUpdateRequest,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminTagOut:
    t = db.get(Tag, tag_id)
    if not t:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    new_name = body.name.strip()
    if not new_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Название тега не может быть пустым",
        )
    clash = db.scalar(
        select(Tag.id).where(
            Tag.group_id == t.group_id,
            Tag.name == new_name,
            Tag.id != t.id,
        ),
    )
    if clash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Тег с таким именем уже есть в этой группе",
        )
    t.name = new_name
    db.commit()
    db.refresh(t)
    gsl = t.group.slug if t.group else None
    return AdminTagOut(
        id=t.id,
        name=t.name,
        type=t.type,
        group_id=t.group_id,
        group_slug=gsl,
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> AdminUserListResponse:
    _ = _su
    total = db.scalar(select(func.count()).select_from(User)) or 0
    rows = db.scalars(
        select(User).order_by(User.created_at.desc()).offset(skip).limit(limit),
    ).all()
    return AdminUserListResponse(
        items=[
            AdminUserOut(
                id=u.id,
                phone=u.phone,
                display_name=u.display_name,
                role=u.role,
                created_at=u.created_at,
                last_login_at=u.last_login_at,
            )
            for u in rows
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("/users", response_model=AdminUserOut)
def create_user(
    body: AdminUserCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminUserOut:
    _ = _su
    phone = body.phone.strip()
    existing = db.execute(select(User).where(User.phone == phone)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone already registered",
        )
    dn = None
    if body.display_name is not None:
        s = body.display_name.strip()
        dn = s if s else None
    u = User(
        phone=phone,
        display_name=dn,
        pin_hash=hash_pin(body.pin.strip()),
        role=body.role,
    )
    db.add(u)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone already registered",
        )
    db.refresh(u)
    return AdminUserOut(
        id=u.id,
        phone=u.phone,
        display_name=u.display_name,
        role=u.role,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )


@router.get("/users/{user_id}/detail", response_model=AdminUserDetailOut)
def get_user_detail(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminUserDetailOut:
    _ = _su
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    uid = user_id
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

    user_out = AdminUserOut(
        id=u.id,
        phone=u.phone,
        display_name=u.display_name,
        role=u.role,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )
    return AdminUserDetailOut(
        user=user_out,
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
    )


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: uuid.UUID,
    body: AdminUserUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminUserOut:
    _ = _su
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if body.phone is not None:
        new_phone = body.phone.strip()
        if new_phone != u.phone:
            clash = db.execute(select(User).where(User.phone == new_phone)).scalar_one_or_none()
            if clash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Phone already in use",
                )
            u.phone = new_phone

    if (
        body.role == UserRole.worker.value
        and u.role != UserRole.worker.value
        and body.pin is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="При назначении роли сотрудника задайте новый PIN (6 цифр)",
        )

    role_for_pin = body.role if body.role is not None else u.role
    if body.pin is not None:
        _pin_validation_http(role_for_pin, body.pin)
        u.pin_hash = hash_pin(body.pin.strip())

    if body.role is not None:
        u.role = body.role

    if body.display_name is not None:
        s = body.display_name.strip()
        u.display_name = s if s else None

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone already in use",
        )
    db.refresh(u)
    return AdminUserOut(
        id=u.id,
        phone=u.phone,
        display_name=u.display_name,
        role=u.role,
        created_at=u.created_at,
        last_login_at=u.last_login_at,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> Response:
    """Удаление через SQL DELETE: ORM session.delete(user) иногда даёт 500 при каскадах/expire."""
    _ = _su
    try:
        result = db.execute(delete(User).where(User.id == user_id))
        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        log.warning("delete_user integrity_error user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя удалить пользователя: в БД остались связанные записи.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        log.exception("delete_user failed user_id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка базы при удалении пользователя.",
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/brands", response_model=AdminBrandListResponse)
def list_brands(
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminBrandListResponse:
    _ = _principal
    rows = db.scalars(select(Brand).order_by(Brand.name.asc())).all()
    return AdminBrandListResponse(
        items=[
            AdminBrandOut(id=b.id, name=b.name, created_at=b.created_at) for b in rows
        ],
    )


@router.post("/brands", response_model=AdminBrandOut)
def create_brand(
    body: AdminBrandCreateRequest,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> AdminBrandOut:
    _ = _principal
    name = body.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите название бренда",
        )
    b = Brand(name=name)
    db.add(b)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Бренд с таким названием уже есть",
        ) from None
    db.refresh(b)
    return AdminBrandOut(id=b.id, name=b.name, created_at=b.created_at)


@router.get("/fitting-requests", response_model=AdminFittingRequestListResponse)
def list_fitting_requests(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> AdminFittingRequestListResponse:
    _ = _su
    total = db.scalar(select(func.count()).select_from(FittingRequest)) or 0
    rows = db.scalars(
        select(FittingRequest)
        .order_by(FittingRequest.created_at.desc())
        .offset(skip)
        .limit(limit)
        .options(selectinload(FittingRequest.liked_photos)),
    ).all()
    return AdminFittingRequestListResponse(
        items=[
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
            )
            for row in rows
        ],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/campaigns", response_model=AdminCampaignListResponse)
def list_campaigns(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminCampaignListResponse:
    _ = _su
    visit_map = {
        cid: visits for cid, _name, _slug, visits in _campaign_visit_rows(db)
    }
    campaigns = db.scalars(
        select(MarketingCampaign).order_by(MarketingCampaign.created_at.desc()),
    ).all()
    return AdminCampaignListResponse(
        public_app_url=settings.public_app_url.rstrip("/"),
        items=[
            _campaign_out(c, visits=visit_map.get(c.id, 0)) for c in campaigns
        ],
    )


@router.post("/campaigns", response_model=AdminCampaignOut, status_code=status.HTTP_201_CREATED)
def create_campaign(
    body: AdminCampaignCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminCampaignOut:
    _ = _su
    try:
        path = normalize_campaign_path(body.path)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    raw_slug = body.slug.strip() if body.slug else body.name
    try:
        slug = normalize_campaign_slug(raw_slug)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    c = MarketingCampaign(name=body.name.strip(), slug=slug, path=path)
    db.add(c)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Кампания с таким slug уже есть",
        ) from None
    db.refresh(c)
    return _campaign_out(c, visits=0)


@router.get("/campaigns/attribution-debug", response_model=AdminAttributionDebugOut)
def attribution_debug(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
    limit: int = Query(25, ge=1, le=100),
) -> AdminAttributionDebugOut:
    _ = _su
    visit_map = {
        cid: visits for cid, _name, _slug, visits in _campaign_visit_rows(db)
    }
    campaigns = db.scalars(
        select(MarketingCampaign).order_by(MarketingCampaign.created_at.desc()),
    ).all()
    rows = db.execute(
        select(
            UserSession.id,
            UserSession.created_at,
            MarketingCampaign.slug,
            MarketingCampaign.name,
        )
        .outerjoin(MarketingCampaign, MarketingCampaign.id == UserSession.campaign_id)
        .where(UserSession.campaign_id.is_not(None))
        .order_by(UserSession.created_at.desc())
        .limit(limit),
    ).all()
    return AdminAttributionDebugOut(
        campaigns=[_campaign_out(c, visits=visit_map.get(c.id, 0)) for c in campaigns],
        recent_attributed_sessions=[
            AdminAttributionDebugSession(
                session_id=r[0],
                created_at=r[1],
                campaign_slug=r[2],
                campaign_name=r[3],
            )
            for r in rows
        ],
        hint=(
            "Заход считается при создании сессии с ?ref= (без регистрации). "
            "Повторный визит в том же браузере не создаёт новую сессию — для теста "
            "используйте режим инкогнито или очистите данные сайта."
        ),
    )


