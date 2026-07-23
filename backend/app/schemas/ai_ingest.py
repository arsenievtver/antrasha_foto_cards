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
    source_mode: str = "flatlay"
    brand_id: uuid.UUID | None = None
    brand_name: str | None = None
    show_badge: bool = False
    original_filename: str
    status: str
    error_message: str | None
    result_url: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


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


class AiIngestDiagnosticsOut(BaseModel):
    """Проверка с сервера (не из браузера): доступность хоста Fashn по TCP."""

    api_fashn_tcp_443_ok: bool
    api_fashn_tcp_error: str | None = None
    hint: str = (
        "Запросы к api.fashn.ai выполняет только Python-бэкенд (воркер), ключ из FASHN_API_KEY на сервере. "
        "Фронт передаёт только файлы на ваш API."
    )
