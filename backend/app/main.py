import asyncio
import logging

from sqlalchemy.exc import ProgrammingError

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import DOTENV_LOADED_PATHS, settings
from app.logging_config import setup_logging
from app.database import SessionLocal
from app.routers import admin, admin_ai_ingest, auth, feed, guest, interactions, internal_sync, sessions, ximilar
from app.services.ai_ingest_worker import reset_stale_processing_jobs
from app.services.yc_photo_sync import run_sync_job_commit

log = logging.getLogger("app.main")

async def _yc_auto_sync_loop() -> None:
    interval_sec = max(60, settings.yc_auto_sync_interval_minutes * 60)
    await asyncio.sleep(45)
    while True:
        try:
            if settings.yc_s3_configured:
                await asyncio.to_thread(
                    lambda: run_sync_job_commit(
                        settings,
                        deactivate_not_in_bucket=True,
                    ),
                )
            else:
                log.warning("yc_auto_sync: пропуск — S3 ключи не заданы")
        except Exception:
            log.exception("yc_auto_sync: ошибка синхронизации с Object Storage")
        await asyncio.sleep(interval_sec)


async def lifespan(_app: FastAPI):
    setup_logging()
    log.info(
        "Antrasha API старт, LOG_LEVEL=%s, yc_auto_sync_interval_minutes=%s",
        settings.log_level,
        settings.yc_auto_sync_interval_minutes,
    )
    log.info(
        ".env подхвачен из (если список пуст — переменные только из окружения ОС): %s | "
        "FASHN_API_KEY задан=%s | API_XIMILAR (эксп.) задан=%s",
        [str(p) for p in DOTENV_LOADED_PATHS],
        settings.fashn_configured,
        settings.ximilar_configured,
    )
    db_boot = SessionLocal()
    try:
        try:
            reset_stale_processing_jobs(db_boot, older_than_minutes=90)
        except ProgrammingError:
            db_boot.rollback()
            log.warning(
                "lifespan: reset_stale_processing_jobs пропущен — БД без миграций или нет таблицы ai_ingest_jobs; выполните alembic upgrade head",
            )
    finally:
        db_boot.close()

    task: asyncio.Task | None = None
    if settings.yc_auto_sync_interval_minutes > 0:
        task = asyncio.create_task(_yc_auto_sync_loop())
        log.info("Фоновая синхронизация Object Storage включена")
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Antrasha API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(guest.router)
app.include_router(feed.router)
app.include_router(interactions.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(admin_ai_ingest.router)
app.include_router(internal_sync.router)
app.include_router(ximilar.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ping/")
def ping() -> dict[str, str]:
    return {"status": "ok"}

