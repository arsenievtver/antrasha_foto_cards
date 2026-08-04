"""MoySklad Remap 1.2 REST client (barcode lookup + product images)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

from app.externals.http.base import BaseApiClient
from app.externals.http.exceptions import ApiClientAbortableException

log = logging.getLogger("app.moysklad")

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MoySkladProductRef:
    product_id: str
    name: str
    article: str | None
    code: str | None
    barcode: str
    entity_type: str  # product | variant
    variant_id: str | None = None
    path_name: str | None = None
    gender: str | None = None  # male | female | None


_LEAF_FEMALE_RE = re.compile(r"(^|[\s/(])жен(\.|$|[\s)])", re.IGNORECASE)
_LEAF_MALE_RE = re.compile(r"(^|[\s/(])муж(\.|$|[\s)])", re.IGNORECASE)
_FEMALE_TYPE_RE = re.compile(
    r"\b(блуз|плать|сарафан|юбк|топ|туник|леггинс)\w*",
    re.IGNORECASE,
)


def infer_gender(
    path_name: str | None = None,
    *,
    folder_name: str | None = None,
    product_name: str | None = None,
) -> str | None:
    """Infer male/female from MoySklad folder path (Мужская/Женская коллекция)."""
    blob = " ".join(x for x in (path_name, folder_name) if x).casefold()
    if "женск" in blob:
        return "female"
    if "мужск" in blob:
        return "male"
    if blob.rstrip().endswith(" жен") or _LEAF_FEMALE_RE.search(blob):
        return "female"
    if blob.rstrip().endswith(" муж") or _LEAF_MALE_RE.search(blob):
        return "male"

    name = (product_name or "").casefold()
    if not name:
        return None
    if "женск" in name or _LEAF_FEMALE_RE.search(name) or name.rstrip().endswith(" жен."):
        return "female"
    if "мужск" in name or _LEAF_MALE_RE.search(name) or name.rstrip().endswith(" муж."):
        return "male"
    if _FEMALE_TYPE_RE.search(name):
        return "female"
    return None


def _id_from_href(href: str | None) -> str | None:
    if not href:
        return None
    path = unquote(str(href).rstrip("/"))
    tail = path.rsplit("/", 1)[-1]
    if _UUID_RE.fullmatch(tail):
        return tail.lower()
    m = _UUID_RE.search(path)
    return m.group(0).lower() if m else None


def _first_barcode_value(row: dict[str, Any], preferred: str | None = None) -> str | None:
    preferred_norm = (preferred or "").strip()
    barcodes = row.get("barcodes")
    if not isinstance(barcodes, list):
        return preferred_norm or None
    values: list[str] = []
    for item in barcodes:
        if isinstance(item, dict):
            for key in ("barcode", "ean13", "ean8", "code128", "gtin", "upc"):
                raw = item.get(key)
                if raw is not None and str(raw).strip():
                    values.append(str(raw).strip())
                    break
        elif item is not None and str(item).strip():
            values.append(str(item).strip())
    if preferred_norm:
        for v in values:
            if v == preferred_norm:
                return v
    return values[0] if values else (preferred_norm or None)


class MoySkladClient(BaseApiClient):
    BASE_URL = "https://api.moysklad.ru/api/remap/1.2/"
    request_timeout_seconds = 120

    def __init__(self, token: str, *, keep_session: bool = False) -> None:
        super().__init__(keep_session=keep_session)
        self._token = token.strip()

    @property
    def base_url(self) -> str:
        return self.BASE_URL

    @property
    def base_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Accept-Encoding": "gzip",
            "Content-Type": "application/json",
        }

    async def _product_article(self, product_id: str) -> str | None:
        """Артикул часто живёт на родительском товаре, а не на модификации."""
        try:
            resp = await self.get(f"/entity/product/{product_id}")
        except ApiClientAbortableException as e:
            log.warning(
                "moysklad product article product=%s HTTP %s",
                product_id,
                e.response.status,
            )
            return None
        data = resp.parsed_response if isinstance(resp.parsed_response, dict) else {}
        raw = data.get("article")
        if raw is None:
            return None
        text = str(raw).strip()
        return text or None

    async def find_by_barcode(self, barcode: str) -> MoySkladProductRef:
        code = barcode.strip()
        if not code:
            raise ValueError("barcode is empty")

        try:
            resp = await self.get(
                "/entity/assortment",
                params={
                    "filter": f"barcode={code}",
                    "limit": 1,
                    "expand": "product",
                },
            )
        except ApiClientAbortableException as e:
            log.warning(
                "moysklad assortment barcode=%s HTTP %s body=%s",
                code,
                e.response.status,
                str(e.parsed_response)[:400],
            )
            raise

        data = resp.parsed_response or {}
        rows = data.get("rows") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not rows:
            raise LookupError(f"Товар со штрихкодом {code} не найден")

        row = rows[0]
        if not isinstance(row, dict):
            raise LookupError(f"Товар со штрихкодом {code} не найден")

        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        entity_type = str(meta.get("type") or "").strip().lower() or "product"
        entity_id = _id_from_href(meta.get("href")) or str(row.get("id") or "").strip().lower()
        if not entity_id:
            raise RuntimeError("MoySklad: assortment row without id")

        product_id = entity_id
        variant_id: str | None = None
        parent_product = row.get("product") if isinstance(row.get("product"), dict) else {}
        if entity_type == "variant":
            variant_id = entity_id
            p_meta = parent_product.get("meta") if isinstance(parent_product.get("meta"), dict) else {}
            product_id = _id_from_href(p_meta.get("href")) or str(parent_product.get("id") or "").strip().lower()
            if not product_id:
                raise RuntimeError("MoySklad: variant without parent product id")

        name = str(row.get("name") or "").strip() or "Без названия"
        article_raw = row.get("article")
        if (article_raw is None or not str(article_raw).strip()) and parent_product:
            article_raw = parent_product.get("article")
        article = (
            str(article_raw).strip()
            if article_raw is not None and str(article_raw).strip()
            else None
        )
        # У модификаций артикул часто только у родителя — дотягиваем отдельно.
        if not article and product_id and entity_type == "variant":
            article = await self._product_article(product_id)

        code_raw = row.get("code")
        found_barcode = _first_barcode_value(row, preferred=code) or code
        path_raw = row.get("pathName")
        path_name = str(path_raw).strip() if path_raw is not None and str(path_raw).strip() else None
        folder_name: str | None = None
        pf = row.get("productFolder")
        if isinstance(pf, dict):
            fn = pf.get("name")
            if fn is not None and str(fn).strip():
                folder_name = str(fn).strip()
        gender = infer_gender(path_name, folder_name=folder_name, product_name=name)

        return MoySkladProductRef(
            product_id=product_id,
            name=name,
            article=article,
            code=str(code_raw).strip() if code_raw is not None and str(code_raw).strip() else None,
            barcode=found_barcode,
            entity_type=entity_type,
            variant_id=variant_id,
            path_name=path_name,
            gender=gender,
        )

    async def upload_product_image(
        self,
        product_id: str,
        *,
        filename: str,
        content_b64: str,
    ) -> list[dict[str, Any]]:
        pid = product_id.strip()
        fname = filename.strip()
        content = content_b64.strip()
        if content.startswith("data:") and "," in content:
            content = content.split(",", 1)[1].strip()
        if not pid or not fname or not content:
            raise ValueError("product_id, filename and content are required")

        try:
            resp = await self.post(
                f"/entity/product/{pid}/images",
                json={"filename": fname, "content": content},
            )
        except ApiClientAbortableException as e:
            log.warning(
                "moysklad upload image product=%s HTTP %s body=%s",
                pid,
                e.response.status,
                str(e.parsed_response)[:400],
            )
            raise

        parsed = resp.parsed_response
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict) and isinstance(parsed.get("rows"), list):
            return parsed["rows"]
        raise RuntimeError(f"MoySklad: unexpected images response: {type(parsed)}")
