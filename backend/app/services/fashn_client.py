"""Клиент Fashn API (product-to-model)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import Settings

log = logging.getLogger("app.fashn")

# Одна сессия на процесс: connection pooling + urllib3 retries на обрывах TLS/сети.
_FASHN_SESSION: requests.Session | None = None


def _get_fashn_session() -> requests.Session:
    global _FASHN_SESSION
    if _FASHN_SESSION is None:
        retry = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=0.6,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=8)
        s = requests.Session()
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        _FASHN_SESSION = s
    return _FASHN_SESSION

RUN_URL = "https://api.fashn.ai/v1/run"
STATUS_URL = "https://api.fashn.ai/v1/status/{}"

POLL_INTERVAL_SEC = 3.0
TIMEOUT_SEC = 300.0
MAX_RETRIES = 2

ASPECT_RATIO = "4:5"
RESOLUTION = "1k"
NUM_IMAGES = 1
SEED = 42

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_PROMPT_CACHE: dict[str, str] = {}


def _timeout(settings: Settings, read_sec: float) -> tuple[float, float]:
    """Connect / read для requests (тяжёлый POST на submit нуждается в большом read)."""
    return (settings.fashn_http_connect_timeout, read_sec)


def _proxies(settings: Settings) -> dict[str, str] | None:
    p = settings.fashn_https_proxy
    if not p or not str(p).strip():
        return None
    u = str(p).strip()
    return {"http": u, "https": u}


def _prompt_filename_for_gender(gender: str) -> str:
    g = gender.strip().lower()
    if g == "male":
        return "promt_male.txt"
    if g == "female":
        return "promt_female.txt"
    raise ValueError("gender must be male or female")


def load_prompt_for_gender(gender: str) -> str:
    key = gender.strip().lower()
    if key in _PROMPT_CACHE:
        return _PROMPT_CACHE[key]
    name = _prompt_filename_for_gender(gender)
    path = _PROMPTS_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"Prompt file missing: {path}")
    text = path.read_text(encoding="utf-8")
    _PROMPT_CACHE[key] = text
    return text


def submit_job(settings: Settings, *, product_image_data_url: str, prompt: str) -> tuple[str | None, str | None]:
    api_key = settings.fashn_api_key
    if not api_key or not str(api_key).strip():
        return None, "FASHN_API_KEY не задан"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model_name": "product-to-model",
        "inputs": {
            "product_image": product_image_data_url,
            "prompt": prompt,
            "aspect_ratio": ASPECT_RATIO,
            "resolution": RESOLUTION,
            "num_images": NUM_IMAGES,
            "output_format": "png",
            "return_base64": False,
            "seed": SEED,
        },
    }
    session = _get_fashn_session()
    timeout = _timeout(settings, settings.fashn_http_read_timeout_submit)
    proxies = _proxies(settings)
    # Отдельный цикл на SSLError/ConnectionError: часть обрывов TLS urllib3 не классифицирует как retry.
    wire_attempts = 4
    r: requests.Response | None = None
    last_tx_err: str | None = None
    for wire in range(wire_attempts):
        try:
            r = session.post(
                RUN_URL,
                headers=headers,
                json=payload,
                timeout=timeout,
                proxies=proxies,
            )
            break
        except (
            requests.exceptions.SSLError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
        ) as e:
            last_tx_err = str(e)
            log.warning(
                "fashn POST /v1/run wire try %s/%s: %s",
                wire + 1,
                wire_attempts,
                e,
            )
            if wire == wire_attempts - 1:
                return None, last_tx_err
            time.sleep(0.5 * (2**wire))
        except requests.RequestException as e:
            return None, str(e)
    if r is None:
        return None, last_tx_err or "не удалось отправить запрос в Fashn"
    if r.status_code != 200:
        return None, r.text[:2000]
    data = r.json()
    jid = data.get("id")
    if not jid:
        return None, "Ответ Fashn без id"
    fj = str(jid)
    log.info(
        "fashn submit OK remote_id=%s… (полный id длиной %s)",
        fj[:10],
        len(fj),
    )
    return fj, None


def poll_status(settings: Settings, job_id: str) -> tuple[list[str], str | None]:
    api_key = settings.fashn_api_key
    if not api_key:
        return [], "FASHN_API_KEY не задан"
    headers = {"Authorization": f"Bearer {api_key.strip()}"}
    started = time.monotonic()
    next_status_log_at = 0.0
    while True:
        if time.monotonic() - started > TIMEOUT_SEC:
            return [], "Timeout ожидания Fashn"
        try:
            r = _get_fashn_session().get(
                STATUS_URL.format(job_id),
                headers=headers,
                timeout=_timeout(settings, settings.fashn_http_read_timeout_poll),
                proxies=_proxies(settings),
            )
        except requests.RequestException as e:
            return [], str(e)
        if r.status_code != 200:
            return [], r.text[:2000]
        data = r.json()
        status = data.get("status")
        now = time.monotonic()
        if now >= next_status_log_at:
            log.info(
                "fashn poll remote_id=%s… api_status=%s elapsed=%.0fs / %.0fs max",
                str(job_id)[:12],
                status,
                now - started,
                TIMEOUT_SEC,
            )
            next_status_log_at = now + 45.0
        if status == "completed":
            out = data.get("output") or []
            if isinstance(out, list):
                return [str(u) for u in out if u], None
            return [], "Некорректный output"
        if status == "failed":
            return [], str(data.get("error") or data)[:2000]
        time.sleep(POLL_INTERVAL_SEC)


def download_png_bytes(url: str, *, settings: Settings) -> tuple[bytes | None, str | None]:
    try:
        r = _get_fashn_session().get(
            url,
            timeout=_timeout(settings, settings.fashn_http_read_timeout_download),
            proxies=_proxies(settings),
        )
    except requests.RequestException as e:
        return None, str(e)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    return r.content, None


def run_product_to_model_png(settings: Settings, *, gender: str, product_image_data_url: str) -> tuple[bytes | None, str | None]:
    """Полный цикл с ретраями submit/poll/download."""
    prompt = load_prompt_for_gender(gender)
    last_err = "Неизвестная ошибка"
    for attempt in range(MAX_RETRIES):
        log.info(
            "fashn product-to-model попытка %s/%s gender=%s",
            attempt + 1,
            MAX_RETRIES,
            gender,
        )
        jid, err = submit_job(settings, product_image_data_url=product_image_data_url, prompt=prompt)
        if err:
            last_err = err
            log.warning("fashn submit attempt %s: %s", attempt + 1, err)
            continue
        urls, err = poll_status(settings, jid)
        if err:
            last_err = err
            log.warning("fashn poll attempt %s: %s", attempt + 1, err)
            continue
        if not urls:
            last_err = "Пустой output"
            continue
        png, derr = download_png_bytes(urls[0], settings=settings)
        if derr or not png:
            last_err = derr or "Пустые байты"
            continue
        return png, None
    return None, last_err
