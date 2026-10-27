"""Разбор названий и групп МойСклад: пол, категория, бренд, размер, месяц прихода."""

from __future__ import annotations

import re
from datetime import date

ARRIVAL_RE = re.compile(r"/(\d{2})\.(\d{2})(?:\s|$)")
SEASON_RE = re.compile(r"(ВЛ|ОЗ)\s*(20\d\d)")
SIZE_RE = re.compile(r"(\d{2,3}([/-]\d{2,3})?|X{0,3}S|M|X{0,4}L|\d?XL|one ?size|OS)", re.I)
LETTER_SIZES = {"XXS": 0, "XS": 1, "S": 2, "M": 3, "L": 4, "XL": 5, "XXL": 6, "2XL": 6, "XXXL": 7, "3XL": 7}

CANON = [
    (r"брюк|джинс", "Брюки, джинсы"),
    (r"бридж|шорт", "Бриджи, шорты"),
    (r"футболк|поло|топ", "Футболки, поло, топы"),
    (r"рубаш|блуз", "Рубашки, блузки"),
    (r"трикотаж", "Трикотаж"),
    (r"верхн", "Верхняя одежда"),
    (r"пиджак|жакет|бомбер", "Пиджаки, жакеты"),
    (r"костюм", "Костюмы"),
    (r"плать", "Платья"),
    (r"юбк", "Юбки"),
    (r"обувь", "Обувь"),
]

CERTIFICATE_TOP_FOLDERS = {"Сертификат", "Сертификаты"}
NON_ASSORTMENT_TOP_FOLDERS = CERTIFICATE_TOP_FOLDERS | {"Товар ТО"}


def gender_of(path: str) -> str:
    p = (path or "").lower()
    if "муж" in p:
        return "M"
    if "жен" in p or "ланжери" in p or "платья" in p:
        return "W"
    return "-"


def category_of(path: str) -> str:
    """Одна категория для основной ветки, «Онлайн», «РАДУГА»; бельё и аксессуары — по листу группы."""
    path = path or ""
    leaf = re.sub(r"\s+(муж|жен|ТО|Радуга)$", "", path.split("/")[-1], flags=re.I).strip() or path
    if path.startswith("Нижнее белье"):
        return leaf
    tail = "/".join(path.split("/")[1:]) if "/" in path else path
    for pattern, name in CANON:
        if re.search(pattern, tail, re.I):
            return name
    return leaf


def brand_key(name: str | None) -> str | None:
    if not name:
        return None
    return re.sub(r"\s*\((муж|жен)\)\s*$", "", name, flags=re.I).strip().upper() or None


def base_name(variant_name: str | None) -> str:
    """'ART рубашка (ОЗ2024, 44)' → 'ART рубашка'."""
    return re.sub(r"\s*\([^()]*\)\s*$", "", variant_name or "").strip()


def size_of(name: str | None, characteristics: list[dict] | None = None) -> str | None:
    for c in characteristics or []:
        if isinstance(c, dict) and c.get("name") == "Размер" and c.get("value") is not None:
            return str(c["value"]).strip() or None
    m = re.search(r"\(([^()]*)\)\s*$", name or "")
    if not m:
        return None
    last = m.group(1).split(",")[-1].strip()
    return last if SIZE_RE.fullmatch(last) else None


def size_sort_key(size: str) -> tuple:
    m = re.match(r"(\d+)", size or "")
    if m:
        return (0, int(m.group(1)), size)
    return (1, LETTER_SIZES.get((size or "").upper(), 99), size or "")


def arrival_month(article: str | None, name: str | None, today: date) -> date | None:
    """Хвост артикула /ММ.ГГ — месяц прихода модели."""
    m = ARRIVAL_RE.search(f"{article or ''} ") or ARRIVAL_RE.search(f"{name or ''} ")
    if not m:
        return None
    month, yy = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    d = date(2000 + yy, month, 1)
    return d if d <= today else None


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + b.month - a.month


def season_of(variant_name: str | None, first_arrival: date) -> str:
    m = SEASON_RE.search(variant_name or "")
    if m:
        year = int(m.group(2))
        # «ОЗ2027» в названиях ставят товару осени того же календарного года
        if m.group(1) == "ОЗ" and year > first_arrival.year:
            year = first_arrival.year
        return f"{m.group(1)}{year}"
    if first_arrival.month == 12:
        return f"ВЛ{first_arrival.year + 1}"
    if first_arrival.month <= 5:
        return f"ВЛ{first_arrival.year}"
    return f"ОЗ{first_arrival.year}"
