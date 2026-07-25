import re
import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator


def assert_pin_for_role(role: str, pin: str) -> None:
    """Правила: worker — 6 цифр; обычный user (клиент) — 4–12 символов."""
    p = pin.strip()
    if role == "worker":
        if not re.fullmatch(r"\d{6}", p):
            raise ValueError("Для сотрудника PIN должен быть ровно из 6 цифр")
    else:
        if len(p) < 4 or len(p) > 12:
            raise ValueError("PIN клиента: от 4 до 12 символов")


class AdminTagOut(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    group_id: uuid.UUID | None = None
    group_slug: str | None = None
    group_title: str | None = None


class AdminTagGroupOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    min_tags: int
    max_tags: int
    swipe_tier: str = "strong"
    group_sort: int = 0


class AdminTagGroupListResponse(BaseModel):
    items: list[AdminTagGroupOut]


class AdminTagGroupCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    min_tags: int = Field(default=0, ge=0, le=99)
    max_tags: int = Field(default=99, ge=1, le=99)


class AdminTagGroupUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    min_tags: int | None = Field(default=None, ge=0, le=99)
    max_tags: int | None = Field(default=None, ge=1, le=99)
    group_sort: int | None = None


class AdminPhotoTagOut(BaseModel):
    tag_id: uuid.UUID
    name: str
    type: str
    weight: float
    group_slug: str | None = None


class AdminBrandOut(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime


class AdminBrandListResponse(BaseModel):
    items: list[AdminBrandOut]


class AdminBrandCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class AdminFittingRequestOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    display_name: str | None = None
    phone: str
    likes: int
    total: int
    match_rate: float
    note: str | None = None
    status: str
    created_at: datetime
    liked_photos: list[str] = Field(default_factory=list)


class AdminFittingRequestListResponse(BaseModel):
    items: list[AdminFittingRequestOut]
    total: int
    skip: int
    limit: int


class AdminPhotoOut(BaseModel):
    id: uuid.UUID
    url: str
    gender: str
    is_active: bool
    created_at: datetime
    tags: list[AdminPhotoTagOut]
    tagging_uncertain: bool = False
    tagging_review_done: bool = False
    worker_signal_love: bool | None = None
    worker_signal_hit: bool | None = None
    worker_signal_hard: bool | None = None
    brand_id: uuid.UUID | None = None
    brand: str | None = None
    price_segment: str | None = None
    moy_sklad_id: str | None = None
    # Показать центральный бейдж (текст задаётся в feed_settings.card_badge_label).
    show_badge: bool = False
    # Инкремент при сохранении тегов (optimistic locking).
    tags_version: int = 0
    # Очередь разметки: активная бронь другим сотрудником / своя
    claim_expires_at: datetime | None = None
    claim_is_mine: bool = False
    # Счётчики реакций (уникальные «идентичности», см. модель Photo).
    # rating = likes_count - dislikes_count.
    likes_count: int = 0
    dislikes_count: int = 0


class AdminPhotoListResponse(BaseModel):
    items: list[AdminPhotoOut]
    total: int
    skip: int
    limit: int


class AdminPhotosBulkDeleteBody(BaseModel):
    photo_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


class AdminPhotoBulkDeleteItem(BaseModel):
    id: uuid.UUID
    ok: bool
    detail: str | None = None


class AdminPhotosBulkDeleteResponse(BaseModel):
    results: list[AdminPhotoBulkDeleteItem]


class AdminTagListResponse(BaseModel):
    items: list[AdminTagOut]


class AdminTagCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(default="", max_length=50)
    group_id: uuid.UUID | None = None


class AdminTagUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class PhotoTagAssign(BaseModel):
    tag_id: uuid.UUID
    weight: float = 1.0


class AdminPhotoTagsPutBody(BaseModel):
    tags: list[PhotoTagAssign] = Field(default_factory=list)
    worker_signal_love: bool | None = None
    worker_signal_hit: bool | None = None
    worker_signal_hard: bool | None = None
    # Если True — обновить поля brand_id / brand; если False — оставить как в БД (очередь разметки).
    apply_brand: bool = False
    brand_id: uuid.UUID | None = None
    moy_sklad_id: str | None = Field(default=None, max_length=128)
    # Включить/выключить центральный бейдж на карточке.
    show_badge: bool | None = None
    # Явно завершить / снять «размечено». Если не передано — флаг в БД не меняем.
    tagging_review_done: bool | None = None
    # Если передано — должно совпадать с Photo.tags_version, иначе 409 (данные устарели).
    expected_tags_version: int | None = None


class AdminCatalogTagOut(BaseModel):
    id: uuid.UUID
    name: str
    subgroup_key: str | None = None
    sort_order: int = 0
    recommendation_weight: int = 50


class AdminCatalogSubgroupOut(BaseModel):
    key: str | None = None
    label: str
    tags: list[AdminCatalogTagOut]


class AdminCatalogGroupOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    min_tags: int
    max_tags: int
    swipe_tier: str = "strong"
    subgroups: list[AdminCatalogSubgroupOut]


class AdminCatalogSectionOut(BaseModel):
    key: str
    sort: int
    groups: list[AdminCatalogGroupOut]


class AdminTagCatalogResponse(BaseModel):
    """Плоский список групп из БД (title — подпись в разметке). sections — устаревшее, для совместимости."""
    groups: list[AdminCatalogGroupOut] = Field(default_factory=list)
    sections: list[AdminCatalogSectionOut] = Field(default_factory=list)


class AdminWorkerTagCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class AdminCampaignVisitStat(BaseModel):
    campaign_id: uuid.UUID
    name: str
    slug: str
    path: str
    is_active: bool
    tracking_url: str
    visits: int
    visits_7d: int
    visits_30d: int
    engaged_sessions: int
    engagement_rate: float
    interactions: int
    likes: int
    dislikes: int
    registrations: int
    visit_share: float


class AdminStatsOut(BaseModel):
    users: int
    workers: int
    photos: int
    active_photos: int
    tags: int
    interactions: int
    photos_male: int
    photos_female: int
    sessions_total: int
    sessions_with_campaign: int
    sessions_organic: int
    public_app_url: str
    campaign_visits: list[AdminCampaignVisitStat]


class AdminCampaignOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    path: str
    is_active: bool
    created_at: datetime
    tracking_url: str
    visits: int


class AdminCampaignListResponse(BaseModel):
    public_app_url: str
    items: list[AdminCampaignOut]


class AdminCampaignCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(default=None, max_length=64)
    path: str = Field(default="/", max_length=200)


class AdminAttributionDebugSession(BaseModel):
    session_id: uuid.UUID
    created_at: datetime
    campaign_slug: str | None
    campaign_name: str | None


class AdminAttributionDebugOut(BaseModel):
    campaigns: list[AdminCampaignOut]
    recent_attributed_sessions: list[AdminAttributionDebugSession]
    hint: str


class FeedSettingsOut(BaseModel):
    """Политика /feed и единый текст бейджа на карточках."""

    require_tagging_review_for_feed: bool
    card_badge_label: str | None = None


class FeedSettingsPatch(BaseModel):
    require_tagging_review_for_feed: bool | None = None
    # Пустая строка / null — снять текст бейджа (чекбоксы на фото перестанут что-либо показывать).
    card_badge_label: str | None = Field(default=None, max_length=40)


class AdminUserOut(BaseModel):
    id: uuid.UUID
    phone: str
    display_name: str | None = None
    role: str
    admin_permissions: list[str] = Field(default_factory=list)
    created_at: datetime
    last_login_at: datetime | None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserOut]
    total: int
    skip: int
    limit: int


class AdminUserCreateRequest(BaseModel):
    phone: str = Field(min_length=5, max_length=20)
    pin: str = Field(min_length=1)
    role: str = Field(pattern="^(user|worker)$")
    display_name: str | None = Field(default=None, max_length=120)
    admin_permissions: list[str] | None = None

    @model_validator(mode="after")
    def validate_pin(self) -> Self:
        assert_pin_for_role(self.role, self.pin)
        return self


class AdminUserUpdateRequest(BaseModel):
    """Хотя бы одно поле; PIN — только если меняете пароль."""

    phone: str | None = Field(default=None, min_length=5, max_length=20)
    pin: str | None = Field(default=None)
    role: str | None = Field(default=None, pattern="^(user|worker)$")
    display_name: str | None = Field(default=None, max_length=120)
    admin_permissions: list[str] | None = None

    @model_validator(mode="after")
    def normalize_and_require_one(self) -> Self:
        if self.pin is not None and not str(self.pin).strip():
            self.pin = None
        if (
            self.phone is None
            and self.pin is None
            and self.role is None
            and self.display_name is None
            and self.admin_permissions is None
        ):
            raise ValueError(
                "Укажите хотя бы одно поле: phone, pin, role, display_name или admin_permissions"
            )
        return self


class AdminUserTagWeightStat(BaseModel):
    tag_id: uuid.UUID
    tag_name: str
    tag_type: str
    weight: float


class AdminUserTagPairWeightStat(BaseModel):
    tag_a_id: uuid.UUID
    tag_b_id: uuid.UUID
    tag_a_name: str
    tag_b_name: str
    weight: float


class AdminUserDetailOut(BaseModel):
    user: AdminUserOut
    interactions_total: int
    likes: int
    dislikes: int
    interactions_male: int
    interactions_female: int
    likes_male: int
    likes_female: int
    avg_view_time_ms: float | None
    tag_weights: list[AdminUserTagWeightStat]
    tag_pair_weights: list[AdminUserTagPairWeightStat]
