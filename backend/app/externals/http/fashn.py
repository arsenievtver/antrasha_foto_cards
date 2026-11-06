"""Fashn API client (product-to-model)."""

from __future__ import annotations

import asyncio
import logging
import random
import socket
import time
from pathlib import Path
from typing import Callable

import aiohttp
import ujson
from aiohttp import ClientConnectorError, ClientSession, ClientTimeout, TCPConnector

from app.externals.http.base import BaseApiClient
from app.externals.http.exceptions import ApiClientAbortableException

log = logging.getLogger("app.fashn")

POLL_INTERVAL_SEC = 3.0
POLL_TIMEOUT_SEC = 300.0
# TCP + TLS до api.fashn.ai. Тело запроса за это время ещё не ушло,
# поэтому такой обрыв можно повторить без второго платного заказа.
CONNECT_TIMEOUT_SEC = 20.0
SUBMIT_CONNECT_TRIES = 4
# С этого VPS напрямую файл с CDN Fashn целиком не дочитывается: соединение
# замирает после первых килобайт. Кусок в 4 КБ приходит, поэтому без прокси
# PNG собирается из таких кусков.
_DOWNLOAD_CHUNK = 4096
_DOWNLOAD_CHUNK_TRIES = 4

RESOLUTION = "2k"
GENERATION_MODE = "quality"
# Выбор лучшего кадра из нескольких не делаем — стараемся попасть с первого.
NUM_IMAGES = 1
MAX_SEED = 2**32 - 1

# Что делать с остальной одеждой: досочинить вокруг вещи-героя или сохранить весь образ.
# Вешалка это или человек, Fashn видит сам по картинке — в промпте различать не нужно.
CONTENT_MODE_SINGLE = "single"
CONTENT_MODE_LOOK = "look"
VALID_CONTENT_MODES = frozenset({CONTENT_MODE_SINGLE, CONTENT_MODE_LOOK})

# Значения source_mode до миграции 055; старые сборки админки могут ещё их присылать.
_LEGACY_CONTENT_MODES = {
    "flatlay": CONTENT_MODE_SINGLE,
    "on_model": CONTENT_MODE_LOOK,
}

# Куда уедет кадр: свайп-лента PWA или картинка товара в МойСклад.
FRAME_FEED = "feed"
FRAME_OUTLET = "outlet"
VALID_FRAMES = frozenset({FRAME_FEED, FRAME_OUTLET})

# Карточка ленты — 400×700 (≈9:16), картинка товара в МойСклад — 3:4.
# Промах по соотношению съедает пиксели в object-fit: cover ещё до показа.
ASPECT_RATIO_BY_FRAME = {
    FRAME_FEED: "9:16",
    FRAME_OUTLET: "3:4",
}

# Этапы задачи — показываются в админке вместо голого «Обработка».
STAGE_SUBMIT = "submit"
STAGE_GENERATING = "generating"
STAGE_DOWNLOAD = "download"

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"
_PROMPT_PART_CACHE: dict[str, str] = {}

_CONNECT_ERRORS: tuple[type[BaseException], ...] = (ClientConnectorError,)
if hasattr(aiohttp, "ConnectionTimeoutError"):
    _CONNECT_ERRORS = (*_CONNECT_ERRORS, aiohttp.ConnectionTimeoutError)
try:
    from python_socks import ProxyConnectionError, ProxyError, ProxyTimeoutError

    # Ошибки SOCKS-рукопожатия: до Fashn ещё ничего не ушло.
    _CONNECT_ERRORS = (*_CONNECT_ERRORS, ProxyConnectionError, ProxyError, ProxyTimeoutError)
except ImportError:
    pass


class FashnJobFailed(RuntimeError):
    """Fashn сам завершил генерацию ошибкой. Повтор — новый заказ."""


class FashnJobGone(RuntimeError):
    """Заказ или его результат у Fashn больше не найден. Повтор — новый заказ."""


def normalize_content_mode(content_mode: str | None) -> str:
    mode = (content_mode or CONTENT_MODE_SINGLE).strip().lower()
    mode = _LEGACY_CONTENT_MODES.get(mode, mode)
    if mode not in VALID_CONTENT_MODES:
        raise ValueError("content_mode must be single or look")
    return mode


def _content_range_total(value: str) -> int | None:
    if "/" not in value:
        return None
    total = value.rsplit("/", 1)[-1].strip()
    if total.isdigit():
        return int(total)
    return None


def normalize_frame(frame: str | None) -> str:
    f = (frame or FRAME_FEED).strip().lower()
    if f not in VALID_FRAMES:
        raise ValueError("frame must be feed or outlet")
    return f


def _load_prompt_part(name: str) -> str:
    if name in _PROMPT_PART_CACHE:
        return _PROMPT_PART_CACHE[name]
    path = _PROMPTS_DIR / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt part missing: {path}")
    _PROMPT_PART_CACHE[name] = path.read_text(encoding="utf-8").strip()
    return _PROMPT_PART_CACHE[name]


def load_prompt(
    gender: str,
    content_mode: str = CONTENT_MODE_SINGLE,
    frame: str = FRAME_FEED,
) -> str:
    """
    Собирает промпт из блоков в порядке, который советует Fashn: сначала тип кадра
    и субъект, затем правило по содержанию, в конце свет и палитра — хвост длинного
    промпта модель игнорирует, поэтому важное идёт первым.
    """
    g = gender.strip().lower()
    if g not in ("male", "female"):
        raise ValueError("gender must be male or female")
    parts = (
        f"frame_{normalize_frame(frame)}",
        f"model_{g}",
        f"content_{normalize_content_mode(content_mode)}",
        "style",
    )
    return "\n".join(_load_prompt_part(p) for p in parts)


def _noop(*_args) -> None:
    return None


class FashnClient(BaseApiClient):
    BASE_URL = "https://api.fashn.ai/v1/"
    # Иначе сессия режет весь запрос на 30 с, хотя submit рассчитан на сотни секунд.
    request_timeout_seconds = 300

    def __init__(
        self,
        api_key: str,
        *,
        proxy: str | None = None,
        connect_timeout: float = 10.0,
        submit_timeout: float = 60.0,
        poll_timeout: float = 30.0,
        download_timeout: float = 60.0,
    ) -> None:
        super().__init__(keep_session=True)
        self._api_key = api_key.strip()
        self._proxy = proxy or None
        self._connect_timeout = min(connect_timeout, CONNECT_TIMEOUT_SEC)
        self._submit_timeout = submit_timeout
        self._poll_timeout = poll_timeout
        self._download_timeout = download_timeout

    @property
    def _socks(self) -> bool:
        return bool(self._proxy) and self._proxy.lower().startswith("socks")

    @property
    def session(self) -> ClientSession:
        if not self._socks:
            return super().session
        if self._session is None or self._session.closed:
            from aiohttp_socks import ProxyConnector

            # aiohttp сам умеет только HTTP-прокси; SOCKS — через коннектор, DNS на стороне прокси.
            self._session = ClientSession(
                headers=self.base_headers,
                json_serialize=ujson.dumps,
                timeout=ClientTimeout(total=self.request_timeout_seconds),
                connector=ProxyConnector.from_url(self._proxy, rdns=True),
            )
        return self._session

    def _call_timeout(self, total: float) -> ClientTimeout:
        return ClientTimeout(total=total, sock_connect=min(self._connect_timeout, total))

    @property
    def base_url(self) -> str:
        return self.BASE_URL

    @property
    def base_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    def _proxy_kwargs(self) -> dict:
        return {"proxy": self._proxy} if self._proxy and not self._socks else {}

    async def _submit_payload(self, payload: dict, *, label: str) -> str:
        """POST /run один раз. Повтор — только если соединение так и не открылось."""
        last: BaseException | None = None
        for attempt in range(1, SUBMIT_CONNECT_TRIES + 1):
            try:
                resp = await self.post(
                    "/run",
                    json=payload,
                    timeout=self._call_timeout(self._submit_timeout),
                    retry=False,
                    **self._proxy_kwargs(),
                )
                break
            except _CONNECT_ERRORS as e:
                last = e
                log.warning(
                    "fashn %s: соединение не открылось (%s/%s): %s",
                    label,
                    attempt,
                    SUBMIT_CONNECT_TRIES,
                    type(e).__name__,
                )
            except ApiClientAbortableException as e:
                log.warning(
                    "fashn %s HTTP %s body=%s",
                    label,
                    e.response.status,
                    str(e.parsed_response)[:500],
                )
                raise
        else:
            assert last is not None
            raise last
        if resp.status >= 400:
            raise RuntimeError(f"Fashn {label} HTTP {resp.status}: {str(resp.parsed_response)[:300]}")
        log.info("fashn %s HTTP %s body=%s", label, resp.status, str(resp.parsed_response)[:300])
        job_id = (resp.parsed_response or {}).get("id")
        if not job_id:
            raise ValueError(f"Fashn: response missing id (HTTP {resp.status}): {resp.parsed_response}")
        jid = str(job_id)
        log.info("fashn %s OK remote_id=%s…", label, jid[:10])
        return jid

    async def submit(
        self,
        *,
        product_image_data_url: str,
        prompt: str,
        aspect_ratio: str,
        seed: int,
        generation_mode: str = GENERATION_MODE,
    ) -> str:
        """Submits a job to the Fashn API, returns job_id."""
        payload = {
            "model_name": "product-to-model",
            "inputs": {
                "product_image": product_image_data_url,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "resolution": RESOLUTION,
                "generation_mode": generation_mode,
                "num_images": NUM_IMAGES,
                "output_format": "png",
                "return_base64": False,
                "seed": seed,
            },
        }
        return await self._submit_payload(payload, label="submit")

    async def poll_status(self, job_id: str) -> list[str]:
        """Polls job status until completion, returns list of result URLs."""
        started = time.monotonic()
        next_log_at = 0.0
        while True:
            elapsed = time.monotonic() - started
            if elapsed > POLL_TIMEOUT_SEC:
                raise TimeoutError(f"Fashn: polling timeout after {POLL_TIMEOUT_SEC}s (job={job_id})")
            try:
                resp = await self.get(
                    f"/status/{job_id}",
                    timeout=self._call_timeout(self._poll_timeout),
                    **self._proxy_kwargs(),
                )
            except ApiClientAbortableException as e:
                if e.response.status == 404:
                    raise FashnJobGone(f"Fashn: заказ {job_id} не найден") from e
                raise RuntimeError(f"Fashn poll HTTP {e.response.status}") from e

            data: dict = resp.parsed_response or {}
            status = data.get("status")

            now = time.monotonic()
            if now >= next_log_at:
                log.info(
                    "fashn poll id=%s… status=%s elapsed=%.0fs/%.0fs",
                    job_id[:12], status, now - started, POLL_TIMEOUT_SEC,
                )
                next_log_at = now + 45.0

            if status == "completed":
                out = data.get("output") or []
                if not isinstance(out, list):
                    raise ValueError("Fashn: unexpected output format")
                return [str(u) for u in out if u]
            if status == "failed":
                raise FashnJobFailed(f"Fashn job failed: {str(data.get('error') or data)[:500]}")

            await asyncio.sleep(POLL_INTERVAL_SEC)

    async def _download_whole(self, url: str) -> bytes:
        async with self.session.get(
            url,
            timeout=self._call_timeout(self._download_timeout),
            **self._proxy_kwargs(),
        ) as resp:
            if resp.status in (403, 404, 410):
                raise FashnJobGone(f"Fashn download HTTP {resp.status}")
            if resp.status != 200:
                raise RuntimeError(f"Fashn download HTTP {resp.status}")
            return await resp.read()

    async def _download_range(
        self,
        session: ClientSession,
        url: str,
        start: int,
        end: int,
    ) -> tuple[bytes, int | None]:
        timeout = ClientTimeout(total=15, sock_connect=10, sock_read=10)
        headers = {"Range": f"bytes={start}-{end}"}
        last: Exception = RuntimeError("Fashn download: no response")
        for _ in range(_DOWNLOAD_CHUNK_TRIES):
            try:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=timeout,
                    **self._proxy_kwargs(),
                ) as resp:
                    if resp.status in (403, 404, 410):
                        raise FashnJobGone(f"Fashn download HTTP {resp.status}")
                    if resp.status == 206:
                        body = await resp.read()
                        return body, _content_range_total(resp.headers.get("Content-Range", ""))
                    if resp.status == 200:
                        length = resp.content_length or 0
                        if 0 < length <= (end - start + 1):
                            return await resp.read(), length
                        raise RuntimeError(f"Fashn download ignored range, length={length}")
                    raise RuntimeError(f"Fashn download HTTP {resp.status}")
            except FashnJobGone:
                raise
            except Exception as e:
                last = e
                log.warning("fashn download bytes %s-%s: %s", start, end, type(e).__name__)
        raise last

    async def _download_ranges(self, url: str) -> bytes:
        start = 0
        total: int | None = None
        out = bytearray()
        # force_close: каждому куску своё соединение, иначе замирает и оно.
        async with ClientSession(
            connector=TCPConnector(family=socket.AF_INET, force_close=True),
        ) as session:
            while total is None or start < total:
                body, found = await self._download_range(
                    session, url, start, start + _DOWNLOAD_CHUNK - 1
                )
                if not body:
                    raise RuntimeError("Fashn download: empty chunk")
                if found is not None:
                    total = found
                elif len(body) < _DOWNLOAD_CHUNK:
                    total = start + len(body)
                else:
                    raise RuntimeError("Fashn download: range without total size")
                out += body
                start += len(body)
        return bytes(out)

    async def download_png(self, url: str) -> bytes:
        """PNG с CDN Fashn: через прокси целиком, без прокси — кусками."""
        last: Exception = RuntimeError("Fashn download")
        for attempt in range(1, 4):
            try:
                if self._proxy:
                    data = await self._download_whole(url)
                else:
                    data = await self._download_ranges(url)
                if not data:
                    raise RuntimeError("Fashn download: empty file")
                log.info("fashn download ok bytes=%s", len(data))
                return data
            except FashnJobGone:
                raise
            except Exception as e:
                last = e
                log.warning("fashn download %s/3 failed: %s: %s", attempt, type(e).__name__, e)
        raise last

    async def submit_tryon_v16(
        self,
        *,
        model_image: str,
        garment_image: str,
        garment_photo_type: str = "model",
    ) -> str:
        """Virtual try-on v1.6: person + garment → job_id."""
        payload = {
            "model_name": "tryon-v1.6",
            "inputs": {
                "model_image": model_image,
                "garment_image": garment_image,
                "garment_photo_type": garment_photo_type,
                "category": "auto",
                "mode": "quality",
                "segmentation_free": True,
                "output_format": "png",
                "return_base64": False,
            },
        }
        return await self._submit_payload(payload, label="tryon submit")

    async def run_tryon_v16(
        self,
        *,
        model_image: str,
        garment_image: str,
        garment_photo_type: str = "model",
    ) -> bytes:
        """submit → poll → download PNG. Заказ уходит один раз."""
        try:
            job_id = await self.submit_tryon_v16(
                model_image=model_image,
                garment_image=garment_image,
                garment_photo_type=garment_photo_type,
            )
            urls = await self.poll_status(job_id)
            if not urls:
                raise ValueError("Fashn tryon: empty output")
            return await self.download_png(urls[0])
        finally:
            await self.close()

    async def run_product_to_model(
        self,
        *,
        gender: str,
        product_image_url: Callable[[], str],
        content_mode: str = CONTENT_MODE_SINGLE,
        frame: str = FRAME_FEED,
        remote_id: str | None = None,
        on_submitted: Callable[[str], None] = _noop,
        on_stage: Callable[[str], None] = _noop,
    ) -> bytes:
        """
        Заказ → ожидание → PNG. Генерация платная, поэтому заказ уходит один раз.

        remote_id — заказ, который уже оплачен (после рестарта воркера или «Повтора»):
        тогда только ждём и скачиваем. product_image_url вызывается лишь когда
        нужен новый заказ — исходник не грузится в хранилище зря.
        """
        mode = normalize_content_mode(content_mode)
        frm = normalize_frame(frame)
        try:
            urls: list[str] | None = None
            if remote_id:
                on_stage(STAGE_GENERATING)
                try:
                    urls = await self.poll_status(remote_id)
                except FashnJobGone:
                    log.warning("fashn: заказ %s… пропал, нужен новый", remote_id[:12])
                    remote_id = None
            if not remote_id:
                on_stage(STAGE_SUBMIT)
                # Seed на задачу, а не на модуль: на фиксированном seed лента из сотни
                # фото сходилась к одному лицу и одной позе.
                seed = random.randint(0, MAX_SEED)
                log.info(
                    "fashn product-to-model gender=%s content_mode=%s frame=%s aspect=%s "
                    "resolution=%s seed=%s",
                    gender,
                    mode,
                    frm,
                    ASPECT_RATIO_BY_FRAME[frm],
                    RESOLUTION,
                    seed,
                )
                remote_id = await self.submit(
                    product_image_data_url=product_image_url(),
                    prompt=load_prompt(gender, mode, frm),
                    aspect_ratio=ASPECT_RATIO_BY_FRAME[frm],
                    seed=seed,
                )
                on_submitted(remote_id)
                on_stage(STAGE_GENERATING)
                urls = await self.poll_status(remote_id)
            if not urls:
                raise ValueError("Fashn: empty output")
            on_stage(STAGE_DOWNLOAD)
            return await self.download_png(urls[0])
        finally:
            await self.close()
