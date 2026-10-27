"""Разбор названий и групп МойСклад: пол, категория, размер."""

from __future__ import annotations

import re


def gender_of(path: str) -> str:
    p = path.lower()
    if "муж" in p:
        return "M"
    if "жен" in p or "ланжери" in p or "платья" in p:
        return "W"
    return "-"


def category_of(path: str) -> str:
    leaf = path.split("/")[-1] if path else ""
    leaf = re.sub(r"\s+(муж|жен|ТО|Радуга)$", "", leaf, flags=re.I).strip()
    return leaf or path


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


def canon_category(path: str, fallback: str | None) -> str | None:
    """Одна категория для основной ветки, «Онлайн», «Товар ТО» и «РАДУГА»."""
    if path.startswith("Нижнее белье"):
        return fallback
    tail = "/".join(path.split("/")[1:]) if "/" in path else path
    for pattern, name in CANON:
        if re.search(pattern, tail, re.I):
            return name
    return fallback


def brand_key(b: str | None) -> str | None:
    if not b:
        return None
    return re.sub(r"\s*\((муж|жен)\)\s*$", "", b, flags=re.I).strip().upper()


def base_name(variant_name: str) -> str:
    """'ART рубашка (ОЗ2024, 44)' -> 'ART рубашка'."""
    return re.sub(r"\s*\([^()]*\)\s*$", "", variant_name or "").strip()


def size_of(name: str, chars: list[dict] | None) -> str | None:
    for c in chars or []:
        if c.get("name") == "Размер":
            return str(c.get("value")).strip()
    m = re.search(r"\(([^()]*)\)\s*$", name or "")
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).split(",")]
    last = parts[-1] if parts else ""
    if re.fullmatch(r"(\d{2,3}([/-]\d{2,3})?|X{0,3}S|M|X{0,4}L|\d?XL|one ?size|OS)", last, re.I):
        return last
    return None
