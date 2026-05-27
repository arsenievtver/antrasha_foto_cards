from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Tag, TagGroup

_COLOR_EN_TO_RU: dict[str, str] = {
    "grey": "серый", "gray": "серый", "black": "чёрный", "white": "белый",
    "beige": "бежевый", "brown": "коричневый", "blue": "синий", "navy": "синий",
    "light blue": "голубой", "lightblue": "голубой", "green": "зелёный",
    "red": "красный", "burgundy": "бордовый", "bordeaux": "бордовый",
    "pink": "красный", "yellow": "яркий", "orange": "яркий", "purple": "бордовый",
    "multicolor": "яркий", "multicolour": "яркий", "dark": "тёмный",
    "light": "светлый", "bright": "яркий", "pastel": "пастельный",
    "off-white": "белый", "cream": "бежевый", "khaki": "коричневый",
    "tan": "бежевый", "olive": "зелёный", "gold": "яркий", "silver": "серый",
    "ivory": "бежевый",
}

_STYLE_EN_TO_RU: dict[str, str] = {
    "casual": "casual", "classic": "классика", "formal": "деловое",
    "business": "business", "sport": "sport", "sports": "sport",
    "elegant": "вечерний", "evening": "вечерний", "vintage": "ретро",
    "retro": "ретро", "military": "милитари", "street": "streetwear",
    "streetwear": "streetwear", "minimal": "минимализм", "minimalist": "минимализм",
    "boho": "fashion (тренд)", "work": "деловое", "party": "вечерний",
    "smart": "smart casual", "smart casual": "smart casual",
    "fashion": "fashion (тренд)", "trendy": "fashion (тренд)",
    "preppy": "классика", "romantic": "вечерний",
}

_MATERIAL_EN_TO_RU: dict[str, str] = {
    "cotton": "хлопок", "wool": "шерсть", "cashmere": "кашемир", "linen": "лён",
    "silk": "шёлк", "leather": "кожа", "suede": "замша", "denim": "деним",
    "jeans": "деним", "knit": "трикотаж", "knitted": "трикотаж", "mesh": "трикотаж",
    "synthetic": "смесовая", "polyester": "смесовая", "nylon": "смесовая",
    "velvet": "трикотаж", "fleece": "трикотаж", "faux leather": "кожа",
    "faux fur": "смесовая", "melange": "смесовая", "chiffon": "шёлк",
    "denim fabric": "деним",
}

_FIT_EN_TO_RU: dict[str, str] = {
    "slim": "slim", "skinny": "slim", "regular": "regular", "relaxed": "relaxed",
    "loose": "свободный", "oversized": "oversized", "baggy": "свободный",
    "straight": "прямой крой", "tapered": "приталенный", "fitted": "приталенный",
    "tailored": "приталенный", "wide": "свободный", "narrow": "slim",
}

_DESIGN_EN_TO_RU: dict[str, str] = {
    "solid": "однотонный", "plain": "однотонный", "striped": "полоска",
    "stripe": "полоска", "checked": "клетка", "check": "клетка", "plaid": "клетка",
    "print": "принт", "printed": "принт", "graphic": "графика", "logo": "логотип",
    "melange": "меланж", "melange fabric": "меланж", "camouflage": "камуфляж",
    "camo": "камуфляж", "texture": "текстура", "textured": "текстура",
    "embroidered": "принт", "floral": "принт", "pattern": "принт",
    "animal print": "принт", "letter": "надпись", "letters": "надпись",
    "typography": "надпись",
}

_CATEGORY_TAIL_TO_PRODUCT_RU: dict[str, str] = {
    "pants": "брюки", "dresses": "платье", "skirts": "юбка", "shorts": "шорты",
    "upper": "футболка", "jackets and coats": "куртка", "nightwear": "платье",
    "overalls and dungarees": "джинсы", "baby clothes": "футболка",
    "bathrobes": "худи", "polo shirts": "поло", "shirts": "рубашка",
    "blouses": "блузка", "t-shirts": "футболка", "t-shirts & tops": "футболка",
    "sweaters": "свитер", "cardigans": "кардиган", "hoodies": "худи",
    "sweatshirts": "свитшот", "suits": "костюм", "blazers": "пиджак",
    "jeans": "джинсы",
}

_SUB_STR_TO_PRODUCT_RU: list[tuple[str, str]] = [
    ("jean", "джинсы"), ("denim", "джинсы"), ("chino", "чиносы"),
    ("sweat pant", "брюки"), ("track pant", "брюки"), ("cargo", "брюки"),
    ("legging", "брюки"), ("dress", "платье"), ("gown", "платье"),
    ("skirt", "юбка"), ("short", "шорты"), ("polo", "поло"),
    ("oxford shirt", "рубашка"), ("shirt", "рубашка"), ("blouse", "блузка"),
    ("t-shirt", "футболка"), ("tee", "футболка"), ("hoodie", "худи"),
    ("sweatshirt", "свитшот"), ("sweater", "свитер"), ("cardigan", "кардиган"),
    ("blazer", "пиджак"), ("jacket", "жакет"), ("coat", "пальто"),
    ("trench", "тренч"), ("parka", "куртка"), ("puffer", "пуховик"),
    ("down jacket", "пуховик"), ("vest", "жилет"), ("suit", "костюм"),
]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _tail_from_category_path(category: str) -> str:
    if not category or "/" not in category:
        return _norm(category)
    return _norm(category.split("/")[-1])


def _infer_product_type_ru(tags_map: dict[str, str]) -> str | None:
    sub = _norm(tags_map.get("Subcategory", ""))
    cat = tags_map.get("Category", "") or ""
    for needle, ru in _SUB_STR_TO_PRODUCT_RU:
        if needle in sub:
            return ru
    tail = _tail_from_category_path(cat)
    if tail in _CATEGORY_TAIL_TO_PRODUCT_RU:
        return _CATEGORY_TAIL_TO_PRODUCT_RU[tail]
    if "pant" in sub or "pant" in tail:
        return "брюки"
    if "dress" in sub:
        return "платье"
    if "skirt" in sub:
        return "юбка"
    if "short" in sub:
        return "шорты"
    return None


def _lookup_tag(db: Session, group_slug: str, tag_name: str) -> Tag | None:
    tag_name = tag_name.strip()
    if not tag_name:
        return None
    return db.execute(
        select(Tag)
        .join(TagGroup, Tag.group_id == TagGroup.id)
        .where(TagGroup.slug == group_slug, Tag.name == tag_name),
    ).scalar_one_or_none()


@dataclass
class MapResult:
    tag_ids: list[uuid.UUID]
    matched: list[dict[str, Any]]
    unmapped: list[dict[str, str]]


def summarize_tags_map(tags_map: dict[str, Any]) -> str:
    tm = tags_map or {}
    parts = [
        str(p).strip()
        for p in (
            tm.get("Category") or tm.get("Top Category") or "",
            tm.get("Subcategory") or "",
            tm.get("Color") or "",
        )
        if p and str(p).strip()
    ]
    return " · ".join(parts) if parts else "(без тегов)"


def map_tags_map(db: Session, tags_map: dict[str, Any]) -> MapResult:
    merged: dict[str, str] = {
        k: str(v).strip()
        for k, v in (tags_map or {}).items()
        if v is not None and str(v).strip()
    }
    matched: list[dict[str, Any]] = []
    unmapped: list[dict[str, str]] = []
    seen: set[uuid.UUID] = set()

    def add_tag(group_slug: str, ru_name: str, source: str) -> None:
        t = _lookup_tag(db, group_slug, ru_name)
        if not t:
            unmapped.append({"key": source, "value": f"{group_slug}:{ru_name} (нет в каталоге)"})
            return
        if t.id in seen:
            return
        seen.add(t.id)
        matched.append({"tag_id": t.id, "tag_name": t.name, "group_slug": group_slug, "source": source})

    def resolve(mapping: dict[str, str], raw_val: str | None, group: str, key: str) -> None:
        if not raw_val:
            return
        norm = _norm(raw_val)
        ru = mapping.get(norm) or next((v for k, v in mapping.items() if k in norm), None)
        if ru:
            add_tag(group, ru, f"{key}:{raw_val}")
        else:
            unmapped.append({"key": key, "value": raw_val})

    pt = _infer_product_type_ru(merged)
    if pt:
        add_tag("product_type", pt, "Category/Subcategory")

    resolve(_COLOR_EN_TO_RU, merged.get("Color"), "color", "Color")
    resolve(_STYLE_EN_TO_RU, merged.get("Style"), "style", "Style")
    resolve(_MATERIAL_EN_TO_RU, merged.get("Material"), "material", "Material")
    resolve(_FIT_EN_TO_RU, merged.get("Fit"), "fit", "Fit")
    resolve(_DESIGN_EN_TO_RU, merged.get("Design"), "print_visual", "Design")

    return MapResult(tag_ids=list(seen), matched=matched, unmapped=unmapped)


def map_ximilar_records(db: Session, ximilar_json: dict[str, Any]) -> MapResult:
    records = ximilar_json.get("records") or []
    if not records:
        return MapResult(tag_ids=[], matched=[], unmapped=[{"key": "_", "value": "empty records"}])
    merged: dict[str, str] = {}
    for rec in records:
        for obj in rec.get("_objects") or []:
            for k, v in (obj.get("_tags_map") or {}).items():
                if v is not None and str(v).strip():
                    merged[k] = str(v).strip()
    return map_tags_map(db, merged)