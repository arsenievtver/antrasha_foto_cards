from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Не полагаться на cwd: скрипты и uvicorn могут стартовать из разных каталогов.
# Подхватываем оба пути: backend/.env и корень репозитория. Достаточно одного файла — например только
# `<repo>/.env` (типичный кейс: FASHN_API_KEY и прочее лежат в корне).
# Если оба файла есть, pydantic-settings подмешивает оба; при дублирующихся ключах побеждает значение
# из файла, идущего позже в списке (ниже), т.е. корневой .env перекрывает backend/.env.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
_ENV_CANDIDATES = (_BACKEND_DIR / ".env", _REPO_ROOT / ".env")
_ENV_FILES = tuple(p for p in _ENV_CANDIDATES if p.is_file())

# Для диагностики в админке: какие пути к .env проверяются и какие файлы реально переданы в Settings.
DOTENV_CANDIDATE_PATHS: tuple[Path, ...] = _ENV_CANDIDATES
DOTENV_LOADED_PATHS: tuple[Path, ...] = _ENV_FILES


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://antrasha:antrasha@localhost:5433/antrasha"
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    # Access JWT (короткий срок; продление — через refresh).
    jwt_expire_minutes: int = 60 * 24 * 30
    # Refresh JWT для POST /auth/refresh (только role=user/worker, не superuser).
    jwt_refresh_expire_days: int = 180
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:5175,http://127.0.0.1:5175"
    )
    # Базовый URL публичного приложения для ссылок кампаний (?ref=slug)
    public_app_url: str = "http://localhost:5173"

    # Суперпользователь админки: логин + пароль (JWT role=superuser).
    # Задайте username и один из вариантов пароля: хеш bcrypt (как у PIN) или plain только для локальной разработки.
    admin_superuser_username: str | None = None
    admin_superuser_password: str | None = None
    admin_superuser_password_bcrypt: str | None = None

    # Yandex Object Storage (S3 API). Листинг объектов — только со статическими ключами
    # (создаются в консоли Yandex Cloud для сервисного аккаунта). IAM-токен сюда не передаётся.
    yc_s3_endpoint: str = "https://storage.yandexcloud.net"
    yc_s3_region: str = "ru-central1"
    yc_s3_access_key_id: str | None = None
    yc_s3_secret_access_key: str | None = None
    yc_bucket_men: str = "antrasha-men-foto"
    yc_bucket_women: str = "antrasha-women-foto"
    try_on_tmp_dir: str = "/app/var/try_on_tmp"
    # Если файлы лежат под префиксом внутри бакета (не ID каталога в консоли — свой префикс ключей)
    yc_s3_prefix_men: str = ""
    yc_s3_prefix_women: str = ""

    log_level: str = "INFO"
    # Пусто = backend/logs/app.log
    log_app_file: str | None = None

    # POST /internal/sync-object-storage — Bearer-токен (длинная случайная строка)
    internal_sync_secret: str | None = None
    # Периодическая синхронизация бакет → Postgres (0 = выключено)
    yc_auto_sync_interval_minutes: int = 0

    # Ximilar Fashion Tagging (эксперимент) — в .env: API_XIMILAR
    api_ximilar: str | None = Field(
        default=None,
        validation_alias=AliasChoices("API_XIMILAR", "api_ximilar"),
    )

    # MAX Bot API — уведомления о новых заявках на примерку
    max_bot_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MAX_BOT_TOKEN", "max_bot_token"),
    )
    max_notify_user_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices("MAX_NOTIFY_USER_ID", "max_notify_user_id"),
    )

    # Web Push (PWA): VAPID-ключи — scripts/generate_vapid_keys.py
    vapid_public_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPID_PUBLIC_KEY", "vapid_public_key"),
    )
    vapid_private_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPID_PRIVATE_KEY", "vapid_private_key"),
    )
    vapid_claims_sub: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VAPID_CLAIMS_SUB", "vapid_claims_sub"),
    )

    # Anthropic + warehouse AI
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key"),
    )
    anthropic_model: str = Field(
        default="claude-sonnet-4-6",
        validation_alias=AliasChoices("ANTHROPIC_MODEL", "anthropic_model"),
    )
    # semantic (default) | legacy_mcp
    warehouse_ai_mode: str = Field(
        default="semantic",
        validation_alias=AliasChoices("WAREHOUSE_AI_MODE", "warehouse_ai_mode"),
    )
    warehouse_ai_router_model: str = Field(
        default="claude-haiku-4-5",
        validation_alias=AliasChoices(
            "WAREHOUSE_AI_ROUTER_MODEL",
            "warehouse_ai_router_model",
        ),
    )
    warehouse_ai_writer_model: str = Field(
        default="claude-sonnet-4-6",
        validation_alias=AliasChoices(
            "WAREHOUSE_AI_WRITER_MODEL",
            "warehouse_ai_writer_model",
        ),
    )
    anthropic_max_tokens: int = Field(
        default=8192,
        validation_alias=AliasChoices("ANTHROPIC_MAX_TOKENS", "anthropic_max_tokens"),
    )
    anthropic_http_timeout: float = Field(
        default=180.0,
        validation_alias=AliasChoices("ANTHROPIC_HTTP_TIMEOUT", "anthropic_http_timeout"),
    )
    # Если api.anthropic.com режет IP сервера (часто РФ) — HTTPS/SOCKS прокси с выходом в supported region.
    # Пример: http://127.0.0.1:7890 или socks5://user:pass@host:1080 (для SOCKS нужен PySocks).
    anthropic_https_proxy: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_HTTPS_PROXY", "anthropic_https_proxy"),
    )
    moysklad_mcp_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MOYSKLAD_MCP_URL", "moysklad_mcp_url"),
    )
    moysklad_mcp_auth_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MOYSKLAD_MCP_AUTH_TOKEN", "moysklad_mcp_auth_token"),
    )
    moysklad_mcp_server_name: str = Field(
        default="moysklad",
        validation_alias=AliasChoices("MOYSKLAD_MCP_SERVER_NAME", "moysklad_mcp_server_name"),
    )
    # Через запятую: allowlist tools. Пусто = встроенный read-only набор (см. warehouse_ai.py).
    # Значение all / * — все tools с MCP (дорого по токенам).
    moysklad_mcp_allowed_tools: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "MOYSKLAD_MCP_ALLOWED_TOOLS",
            "moysklad_mcp_allowed_tools",
        ),
    )
    moysklad_mcp_denied_tools: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "MOYSKLAD_MCP_DENIED_TOOLS",
            "moysklad_mcp_denied_tools",
        ),
    )
    # Сколько раз продолжать ответ при stop_reason=pause_turn (серверный MCP-цикл).
    anthropic_mcp_max_continues: int = Field(
        default=5,
        validation_alias=AliasChoices(
            "ANTHROPIC_MCP_MAX_CONTINUES",
            "anthropic_mcp_max_continues",
        ),
    )
    # REST API МойСклад (аутлет: штрихкод → товар, загрузка изображений)
    moysklad_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("MOYSKLAD_TOKEN", "moysklad_token"),
    )

    # Fashn AI (product-to-model) — в .env: FASHN_API_KEY
    fashn_api_key: str | None = None
    # Если api.fashn.ai недоступен с IP сервера (например РФ), задайте HTTPS-прокси только для Fashn.
    # Пример: http://127.0.0.1:7890 или socks5://user:pass@host:1080 (для SOCKS добавьте PySocks в окружение).
    # Не путайте с глобальным HTTPS_PROXY — этот прокси держим узким, чтобы Object Storage не шёл через него.
    fashn_https_proxy: str | None = None
    # Таймауты requests к api.fashn.ai: (connect, read). Submit с большим base64 часто >120 с.
    fashn_http_connect_timeout: float = 30.0
    # POST /run: после отправки сырого JPEG тело меньше — 300 с обычно достаточно; при ноде Fashn приподними.
    fashn_http_read_timeout_submit: float = 300.0
    fashn_http_read_timeout_poll: float = 60.0
    fashn_http_read_timeout_download: float = 180.0
    # Очередь телефон → ИИ → Object Storage: лимиты и каталог временных файлов
    ai_ingest_max_files_per_upload: int = 40
    ai_ingest_max_file_bytes: int = 35 * 1024 * 1024
    promo_banner_max_file_bytes: int = 8 * 1024 * 1024
    # Локальные файлы баннеров (1–3 шт., без Object Storage). Пусто = backend/data/promo-banners
    promo_banner_media_dir: str | None = None
    hero_banner_max_file_bytes: int = 8 * 1024 * 1024
    # Полноэкранные hero-баннеры. Пусто = backend/data/hero-banners
    hero_banner_media_dir: str | None = None
    home_v2_max_file_bytes: int = 8 * 1024 * 1024
    # Фото MEN/WOMEN на /v2. Пусто = backend/data/home-v2
    home_v2_media_dir: str | None = None
    ai_ingest_max_pending_jobs: int = 400
    ai_ingest_worker_concurrency: int = 2
    # Пусто = backend/var/ai_ingest_tmp (создаётся при старте загрузки)
    ai_ingest_temp_dir: str | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def yc_s3_configured(self) -> bool:
        return bool(self.yc_s3_access_key_id and self.yc_s3_secret_access_key)

    @property
    def admin_superuser_enabled(self) -> bool:
        if not self.admin_superuser_username or not str(self.admin_superuser_username).strip():
            return False
        return bool(
            (self.admin_superuser_password_bcrypt and self.admin_superuser_password_bcrypt.strip())
            or (self.admin_superuser_password and self.admin_superuser_password.strip())
        )

    @property
    def ai_ingest_temp_path(self) -> Path:
        if self.ai_ingest_temp_dir and str(self.ai_ingest_temp_dir).strip():
            return Path(self.ai_ingest_temp_dir).expanduser().resolve()
        return (_BACKEND_DIR / "var" / "ai_ingest_tmp").resolve()

    @property
    def promo_banner_media_path(self) -> Path:
        if self.promo_banner_media_dir and str(self.promo_banner_media_dir).strip():
            return Path(self.promo_banner_media_dir).expanduser().resolve()
        return (_BACKEND_DIR / "data" / "promo-banners").resolve()

    @property
    def hero_banner_media_path(self) -> Path:
        if self.hero_banner_media_dir and str(self.hero_banner_media_dir).strip():
            return Path(self.hero_banner_media_dir).expanduser().resolve()
        return (_BACKEND_DIR / "data" / "hero-banners").resolve()

    @property
    def home_v2_media_path(self) -> Path:
        if self.home_v2_media_dir and str(self.home_v2_media_dir).strip():
            return Path(self.home_v2_media_dir).expanduser().resolve()
        return (_BACKEND_DIR / "data" / "home-v2").resolve()

    @property
    def web_push_configured(self) -> bool:
        return bool(
            self.vapid_public_key
            and str(self.vapid_public_key).strip()
            and self.vapid_private_key
            and str(self.vapid_private_key).strip()
            and self.vapid_claims_sub
            and str(self.vapid_claims_sub).strip()
        )

    @property
    def max_notify_configured(self) -> bool:
        return bool(
            self.max_bot_token
            and str(self.max_bot_token).strip()
            and self.max_notify_user_id is not None
        )

    @property
    def fashn_configured(self) -> bool:
        return bool(self.fashn_api_key and str(self.fashn_api_key).strip())

    @property
    def ximilar_configured(self) -> bool:
        return bool(self.api_ximilar and str(self.api_ximilar).strip())

    @property
    def warehouse_ai_configured(self) -> bool:
        key = bool(self.anthropic_api_key and str(self.anthropic_api_key).strip())
        if not key:
            return False
        mode = (self.warehouse_ai_mode or "semantic").strip().lower()
        if mode == "legacy_mcp":
            return bool(self.moysklad_mcp_url and str(self.moysklad_mcp_url).strip())
        return bool(self.moysklad_token and str(self.moysklad_token).strip())

    @property
    def moysklad_configured(self) -> bool:
        return bool(self.moysklad_token and str(self.moysklad_token).strip())


settings = Settings()
