"""Внутренние операции (cron, CI): синхронизация фото с Object Storage."""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.services.yc_photo_sync import run_sync_job_commit

router = APIRouter(prefix="/internal", tags=["internal"])
_bearer = HTTPBearer(auto_error=False)


def _require_sync_secret(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    expected = settings.internal_sync_secret
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="INTERNAL_SYNC_SECRET не задан — endpoint отключён",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer token required")
    got = credentials.credentials
    if len(got) != len(expected):
        raise HTTPException(status_code=403, detail="Invalid token")
    if not secrets.compare_digest(got, expected):
        raise HTTPException(status_code=403, detail="Invalid token")


@router.post(
    "/sync-object-storage",
    dependencies=[Depends(_require_sync_secret)],
)
def sync_object_storage() -> dict:
    """Подтянуть состав бакетов в Postgres (как CLI sync). Authorization: Bearer <INTERNAL_SYNC_SECRET>."""
    if not settings.yc_s3_configured:
        raise HTTPException(
            status_code=503,
            detail="Yandex S3 ключи не настроены",
        )
    return run_sync_job_commit(settings, deactivate_not_in_bucket=True)
