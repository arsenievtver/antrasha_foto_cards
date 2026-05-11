import re
import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator


def assert_pin_for_role(role: str, pin: str) -> None:
    """Правила: worker — 6 цифр; обычный user — 4–12 символов."""
    p = pin.strip()
    if role == "worker":
        if not re.fullmatch(r"\d{6}", p):
            raise ValueError("Для сотрудника PIN должен быть ровно из 6 цифр")
    else:
        if len(p) < 4 or len(p) > 12:
            raise ValueError("PIN пользователя: от 4 до 12 символов")


class AdminTagOut(BaseModel):
    id: uuid.UUID
    name: str
    type: str
    group_id: uuid.UUID | None = None
    group_slug: str | None = None


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
    type: str = Field(min_length=1, max_length=50)
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
    sections: list[AdminCatalogSectionOut]


class AdminWorkerTagCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class AdminStatsOut(BaseModel):
    users: int
    workers: int
    photos: int
    active_photos: int
    tags: int
    interactions: int
    photos_male: int
    photos_female: int


class FeedSettingsOut(BaseModel):
    """Политика /feed: требовать ли завершённую разметку перед показом карточки."""

    require_tagging_review_for_feed: bool


class FeedSettingsPatch(BaseModel):
    require_tagging_review_for_feed: bool


class AdminUserOut(BaseModel):
    id: uuid.UUID
    phone: str
    display_name: str | None = None
    role: str
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

    @model_validator(mode="after")
    def normalize_and_require_one(self) -> Self:
        if self.pin is not None and not str(self.pin).strip():
            self.pin = None
        if (
            self.phone is None
            and self.pin is None
            and self.role is None
            and self.display_name is None
        ):
            raise ValueError("Укажите хотя бы одно поле: phone, pin, role или display_name")
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
