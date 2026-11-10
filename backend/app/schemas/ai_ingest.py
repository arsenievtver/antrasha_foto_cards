from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AiIngestLimitsOut(BaseModel):
    max_files_per_upload: int
    max_file_bytes: int
    max_pending_jobs: int
    worker_concurrency: int
    # Ниже — не секреты, чтобы сверить окружение сервера со скриптом у себя на машине.
    fashn_configured: bool = False
    yc_s3_configured: bool = False
    # Оба True → upload разрешён; обработку делает отдельный процесс jobs.ai_ingest_worker.
    pipeline_ready: bool = False
    fashn_calls_from: str = "server_only"
    env_dotenv_candidates: list[str] = []
    env_dotenv_loaded: list[str] = []
    fashn_key_last4: str | None = None
    # Последние 4 символа access key id — сверка, что в процесс попали ваши ключи из env.
    yc_access_key_id_last4: str | None = None


class AiIngestJobOut(BaseModel):
    id: uuid.UUID
    gender: str
    source_mode: str = "single"
    brand_id: uuid.UUID | None = None
    brand_name: str | None = None
    show_badge: bool = False
    original_filename: str
    status: str
    # upload | submit | generating | download | save — пока status=processing.
    stage: str | None = None
    stage_at: datetime | None = None
    # Заказ Fashn уже оплачен: «Повтор» его продолжит, а не закажет новый.
    fashn_ordered: bool = False
    # processing без движения больше 20 минут — можно удалить.
    stale: bool = False
    error_message: str | None
    result_url: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    product_name: str | None = None
    article: str | None = None
    barcode: str | None = None
    supplier_name: str | None = None
    moysklad_product_id: str | None = None
    # linked | name | none — только для кадра с телефона.
    brand_match: str | None = None
    brand_warning: str | None = None
    suggested_brand_id: uuid.UUID | None = None
    suggested_brand_name: str | None = None
    # uploaded | failed | пусто
    moysklad_upload_status: str | None = None
    moysklad_upload_error: str | None = None


class AiIngestUploadResponse(BaseModel):
    created: list[AiIngestJobOut]
    limits: AiIngestLimitsOut


class AiIngestJobListResponse(BaseModel):
    items: list[AiIngestJobOut]
    total: int
    skip: int
    limit: int


class AiIngestQueueStatsOut(BaseModel):
    pending: int
    processing: int
    failed: int
    inbox: int = 0


class AiIngestReleaseDraftOut(BaseModel):
    gender: str
    batch_id: uuid.UUID | None = None
    photo_count: int = 0
    embedded_count: int = 0
    embed_pending: int = 0
    embed_error_count: int = 0
    last_embed_error: str | None = None
    fashn_pending: int = 0
    fashn_failed: int = 0
    moysklad_pending: int = 0
    can_publish: bool = False


class AiIngestPublishOut(BaseModel):
    ok: bool
    published: bool
    batch_id: str | None = None
    photo_count: int = 0
    message: str
    failed: list[dict] = []


class AiIngestEnqueueItem(BaseModel):
    job_id: uuid.UUID
    brand_id: uuid.UUID | None = None


class AiIngestEnqueueIn(BaseModel):
    source_mode: str
    show_badge: bool = False
    items: list[AiIngestEnqueueItem]


class AiIngestEnqueueOut(BaseModel):
    items: list[AiIngestJobOut]


class AiIngestDiagnosticsOut(BaseModel):
    """Проверка с сервера (не из браузера): доступность хоста Fashn по TCP."""

    api_fashn_tcp_443_ok: bool
    api_fashn_tcp_error: str | None = None
    hint: str = (
        "Запросы к api.fashn.ai выполняет только Python-бэкенд (воркер), ключ из FASHN_API_KEY на сервере. "
        "Фронт передаёт только файлы на ваш API."
    )
