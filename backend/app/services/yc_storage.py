from __future__ import annotations

from urllib.parse import quote, unquote, urlparse

import boto3
from botocore.exceptions import ClientError
from botocore.client import BaseClient

from app.config import Settings, settings

_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".heic", ".bmp")


def get_s3_client() -> BaseClient:
    if not settings.yc_s3_configured:
        raise RuntimeError(
            "Yandex Object Storage: задайте YC_S3_ACCESS_KEY_ID и YC_S3_SECRET_ACCESS_KEY в .env"
        )
    session = boto3.session.Session()
    return session.client(
        service_name="s3",
        endpoint_url=settings.yc_s3_endpoint,
        aws_access_key_id=settings.yc_s3_access_key_id,
        aws_secret_access_key=settings.yc_s3_secret_access_key,
        region_name=settings.yc_s3_region,
    )


def public_object_url(bucket: str, key: str) -> str:
    """Публичный URL объекта (нужен публичный чтение бакета или объекта)."""
    encoded = "/".join(quote(segment, safe="") for segment in key.split("/"))
    return f"https://storage.yandexcloud.net/{bucket}/{encoded}"


def parse_storage_public_url(url: str) -> tuple[str, str] | None:
    """
    Обратно к public_object_url: https://storage.yandexcloud.net/<bucket>/<key...>
    """
    if not url or not url.startswith("http"):
        return None
    try:
        u = urlparse(url.strip())
        if u.netloc != "storage.yandexcloud.net":
            return None
        raw = [p for p in u.path.strip("/").split("/") if p != ""]
        if len(raw) < 2:
            return None
        bucket = raw[0]
        key = "/".join(unquote(p) for p in raw[1:])
        return (bucket, key)
    except Exception:
        return None


def delete_object_from_managed_bucket(bucket: str, key: str) -> None:
    """Удаляет объект из бакета (S3 API)."""
    client = get_s3_client()
    client.delete_object(Bucket=bucket, Key=key)


def delete_photo_file_from_object_storage(cfg: Settings, url: str) -> str | None:
    """
    Удаляет файл из Object Storage, если URL указывает на управляемый бакет (муж/жен).
    Возвращает сообщение об ошибке при сбое S3; None — успех или удаление из стораджа не требуется.
    """
    if not cfg.yc_s3_configured:
        return None
    parsed = parse_storage_public_url(url)
    if not parsed:
        return None
    bucket, key = parsed
    allowed = {cfg.yc_bucket_men, cfg.yc_bucket_women}
    if bucket not in allowed:
        return None
    try:
        delete_object_from_managed_bucket(bucket, key)
        return None
    except ClientError as e:
        return str(e)


# S3 Multi-Object Delete лимит — 1000 ключей за запрос.
_S3_DELETE_OBJECTS_MAX_KEYS = 1000


def bulk_delete_photo_files_from_object_storage(
    cfg: Settings,
    urls: list[str],
) -> dict[str, str | None]:
    """
    Пакетное удаление файлов фото из управляемых бакетов.

    Один S3-клиент на весь вызов; один `delete_objects` (Multi-Object Delete)
    на бакет (до 1000 ключей за запрос). Это критично для админского bulk-delete
    — иначе при 50+ фото операция превышает nginx `proxy_read_timeout` (60 с),
    и фронт получает 504, хотя бэкенд продолжает удалять.

    Возвращает: для каждого входного URL — `None` (успех, либо удаление из
    стораджа не требуется), либо текст ошибки S3.
    """
    out: dict[str, str | None] = {u: None for u in urls}
    if not cfg.yc_s3_configured or not urls:
        return out

    allowed = {cfg.yc_bucket_men, cfg.yc_bucket_women}
    # bucket -> key -> [исходные URL, которые ссылаются на этот key]
    keys_by_bucket: dict[str, dict[str, list[str]]] = {}
    for u in urls:
        parsed = parse_storage_public_url(u)
        if not parsed:
            continue
        bucket, key = parsed
        if bucket not in allowed:
            continue
        keys_by_bucket.setdefault(bucket, {}).setdefault(key, []).append(u)

    if not keys_by_bucket:
        return out

    try:
        client = get_s3_client()
    except RuntimeError as e:
        msg = str(e)
        for keys_map in keys_by_bucket.values():
            for url_list in keys_map.values():
                for u in url_list:
                    out[u] = msg
        return out

    for bucket, keys_map in keys_by_bucket.items():
        keys = list(keys_map.keys())
        for i in range(0, len(keys), _S3_DELETE_OBJECTS_MAX_KEYS):
            chunk = keys[i : i + _S3_DELETE_OBJECTS_MAX_KEYS]
            try:
                resp = client.delete_objects(
                    Bucket=bucket,
                    Delete={
                        "Objects": [{"Key": k} for k in chunk],
                        # Quiet=True — в ответе будут только ошибки, успешные ключи опускаются.
                        "Quiet": True,
                    },
                )
            except ClientError as e:
                # Целиком чанк не дошёл — пометим все его URL как «ошибка».
                err_msg = str(e)
                for k in chunk:
                    for u in keys_map.get(k, []):
                        out[u] = err_msg
                continue
            for err in resp.get("Errors", []) or []:
                err_key = err.get("Key", "")
                msg = err.get("Message") or err.get("Code") or "S3 error"
                for u in keys_map.get(err_key, []):
                    out[u] = msg
    return out


def is_image_key(key: str) -> bool:
    if not key or key.endswith("/"):
        return False
    lower = key.lower()
    return any(lower.endswith(s) for s in _IMAGE_SUFFIXES)


def put_image_object(
    bucket: str,
    key: str,
    body: bytes,
    *,
    content_type: str = "image/png",
) -> None:
    client = get_s3_client()
    client.put_object(
        Bucket=bucket,
        Key=key,
        Body=body,
        ContentType=content_type,
    )


def list_image_keys(client: BaseClient, bucket: str, prefix: str) -> list[str]:
    prefix = prefix or ""
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            k = obj.get("Key") or ""
            if is_image_key(k):
                keys.append(k)
    return sorted(keys)
