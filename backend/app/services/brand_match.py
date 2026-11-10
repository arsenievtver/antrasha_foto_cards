"""Сопоставление поставщика МойСклад со справочником брендов.

Id поставщика — источник истины. Совпадение имени только предлагает бренд
и всегда с предупреждением: написание в МойСклад и в базе часто разное.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from app.services.weekly_insight.parse import brand_key


class BrandLike(Protocol):
    id: uuid.UUID
    name: str
    moysklad_id: str | None


def normalize_brand_name(name: str | None) -> str:
    return " ".join((brand_key(name) or "").split())


def normalize_moysklad_id(raw: str | None) -> str | None:
    text = (raw or "").strip().lower()
    return text or None


@dataclass(frozen=True)
class BrandMatch:
    brand_id: uuid.UUID | None
    brand_name: str | None
    # linked — id уже записан на бренд; name — совпало только имя; none — выбирать вручную.
    confidence: str
    warning: str | None


def match_supplier(
    brands: list[BrandLike],
    supplier_id: str | None,
    supplier_name: str | None,
) -> BrandMatch:
    sid = normalize_moysklad_id(supplier_id)
    label = (supplier_name or "").strip()
    key = normalize_brand_name(label)

    if sid:
        linked = next((b for b in brands if normalize_moysklad_id(b.moysklad_id) == sid), None)
        if linked is not None:
            warning = None
            if key and normalize_brand_name(linked.name) != key:
                warning = (
                    f"Привязка по id МойСклад. Поставщик там «{label}», "
                    f"в базе бренд «{linked.name}»."
                )
            return BrandMatch(linked.id, linked.name, "linked", warning)

    if not sid and not key:
        return BrandMatch(
            None,
            None,
            "none",
            "У товара в МойСклад нет поставщика. Выберите бренд вручную.",
        )

    hits = [b for b in brands if key and normalize_brand_name(b.name) == key]
    free = [b for b in hits if not normalize_moysklad_id(b.moysklad_id)]
    taken = [b for b in hits if normalize_moysklad_id(b.moysklad_id)]

    if len(free) == 1 and not taken:
        brand = free[0]
        shown = label or brand.name
        return BrandMatch(
            brand.id,
            brand.name,
            "name",
            (
                f"Название похоже на «{brand.name}», в МойСклад поставщик «{shown}». "
                "Id ещё не записан: проверьте бренд и отправьте в Fashn — id сохранится."
            ),
        )

    if len(hits) > 1:
        names = ", ".join(f"«{b.name}»" for b in hits[:4])
        return BrandMatch(
            None,
            None,
            "none",
            f"Имя «{label or key}» похоже сразу на несколько брендов: {names}. Выберите нужный.",
        )

    if taken and not free:
        brand = taken[0]
        return BrandMatch(
            None,
            None,
            "none",
            (
                f"Название похоже на «{brand.name}», но у этого бренда уже другой id МойСклад. "
                "Выберите бренд вручную."
            ),
        )

    if sid and not label:
        return BrandMatch(
            None,
            None,
            "none",
            f"Поставщик {sid} не привязан к бренду и без названия. Выберите бренд — id сохранится.",
        )

    who = f"«{label}»" if label else "без названия"
    return BrandMatch(
        None,
        None,
        "none",
        f"Поставщик {who} не найден в справочнике. Выберите бренд — id МойСклад запишется в него.",
    )


def apply_supplier_link(brand: BrandLike, supplier_id: str | None, brands: list[BrandLike]) -> str | None:
    """Пишет id поставщика на бренд. None — можно продолжать, строка — отказ."""
    sid = normalize_moysklad_id(supplier_id)
    if not sid:
        return None
    current = normalize_moysklad_id(brand.moysklad_id)
    if current == sid:
        return None
    if current:
        return (
            f"У бренда «{brand.name}» уже другой id МойСклад. "
            "Сбросьте привязку в справочнике или выберите другой бренд."
        )
    for other in brands:
        if other.id != brand.id and normalize_moysklad_id(other.moysklad_id) == sid:
            return f"Этот поставщик уже привязан к бренду «{other.name}»."
    brand.moysklad_id = sid
    return None
