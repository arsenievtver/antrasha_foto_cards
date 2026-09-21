import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RankingEvalPhotoOut(BaseModel):
    photo_id: uuid.UUID
    url: str
    has_embedding: bool
    sort_order: int


class RankingEvalBenchmarkOut(BaseModel):
    id: uuid.UUID
    name: str
    gender: str
    is_active: bool
    created_at: datetime
    photo_count: int = 0
    embedded_count: int = 0


class RankingEvalBenchmarkDetailOut(RankingEvalBenchmarkOut):
    photos: list[RankingEvalPhotoOut] = Field(default_factory=list)


class RankingEvalBenchmarkCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    gender: str = Field(pattern="^(male|female)$")


class RankingEvalBenchmarkPatch(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None


class RankingEvalEmbedBatchOut(BaseModel):
    processed: int
    succeeded: int
    failed: list[dict[str, Any]] = Field(default_factory=list)


class RankingEvalActiveOut(BaseModel):
    benchmark_id: uuid.UUID
    name: str
    gender: str
    photos: list[RankingEvalPhotoOut]
    already_submitted: bool = False


class RankingEvalSubmitRequest(BaseModel):
    benchmark_id: uuid.UUID
    human_order: list[uuid.UUID] = Field(min_length=2, max_length=10)


class RankingEvalSubmitResponse(BaseModel):
    submission_id: uuid.UUID
    kendall_tau: float | None
    spearman_rho: float | None
    top3_overlap: int | None


class RankingEvalSubmissionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    benchmark_id: uuid.UUID
    benchmark_name: str
    gender: str
    user_id: uuid.UUID
    user_label: str
    human_order: list[uuid.UUID]
    model_order: list[uuid.UUID]
    kendall_tau: float | None
    spearman_rho: float | None
    top3_overlap: int | None
    settings_snapshot: dict[str, Any] = Field(default_factory=dict)


class RankingEvalSubmissionDetailOut(RankingEvalSubmissionOut):
    photos: list[RankingEvalPhotoOut] = Field(default_factory=list)
