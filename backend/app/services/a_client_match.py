"""Привязка текста «Спроса» к клиенту А и склейка сообщений одной мысли.

Имена в комментариях часто не совпадают с карточкой: диктовка, ё/е, лишняя буква.
Сопоставление принимает точную фамилию, опечатку в одну букву и, если пол в тексте
однозначный, опечатку в две. Одно только имя («Кристина», «Андрей») клиента не выбирает:
так зовут и сотрудников, и нескольких покупателей.
"""

from __future__ import annotations

import re
from datetime import timedelta

CONTINUE_WITHIN = timedelta(seconds=180)

_FEMALE = frozenset(
    {"была", "приходила", "сказала", "ждала", "взяла", "перестала", "купила", "заходила", "нее", "ей"}
)
_MALE = frozenset(
    {"был", "приходил", "сказал", "ждал", "взял", "перестал", "купил", "заходил", "него", "ему"}
)
# Частые слова заметок. Их нельзя принимать за фамилию с опечаткой.
_STOP = frozenset(
    {
        "ассортимент",
        "ассортиментом",
        "брюки",
        "всегда",
        "гардероб",
        "гардюр",
        "джинсы",
        "европейского",
        "ежедневно",
        "женских",
        "кисловодск",
        "коллекции",
        "коллекция",
        "коллекцию",
        "конечно",
        "магазин",
        "налогов",
        "отвечает",
        "пальто",
        "покупает",
        "покупка",
        "покупки",
        "постоянно",
        "приглашении",
        "приходит",
        "проблем",
        "проблемы",
        "размеров",
        "распродажи",
        "связи",
        "сказал",
        "сказала",
        "телеграмме",
        "трикотаж",
        "трикотажа",
        "устраивает",
        "финансами",
        "человек",
        "черногории",
        "черногория",
    }
)
_MALE_GIVEN = frozenset({"никита", "илья", "кузьма", "данила", "савва", "лёва"})


def norm(value: str | None) -> str:
    text = (value or "").lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text: str) -> list[tuple[str, bool]]:
    out = []
    for raw in re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", text or ""):
        token = norm(raw)
        if token:
            out.append((token, raw[:1].isupper() or raw.isupper()))
    return out


def _lev(a: str, b: str) -> int:
    if abs(len(a) - len(b)) > 2:
        return 9
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _relative_form(token: str, surname: str) -> bool:
    """«Иванов» и «Иванова» — разные люди, не опечатка."""
    if token == surname:
        return False
    short, long = sorted((token, surname), key=len)
    return long.startswith(short) and 0 < len(long) - len(short) <= 2


def _gender_from_name(parts: list[str]) -> str:
    tail = parts[2:]
    if any(p.endswith(("вна", "кызы", "ична")) for p in tail):
        return "f"
    if any(p.endswith(("вич", "оглы", "угли")) for p in tail):
        return "m"
    given = parts[1] if len(parts) > 1 else ""
    if given in _MALE_GIVEN:
        return "m"
    if given.endswith(("а", "я")):
        return "f"
    if given:
        return "m"
    return "u"


def _text_gender(words: set[str]) -> str:
    female = bool(words & _FEMALE)
    male = bool(words & _MALE)
    if female and not male:
        return "f"
    if male and not female:
        return "m"
    return ""


class _Card:
    def __init__(self, raw: dict):
        parts = norm(raw.get("name")).split()
        self.id = str(raw.get("id") or "")
        self.name = raw.get("name") or ""
        self.surname = parts[0] if parts else ""
        self.given = parts[1] if len(parts) > 1 else ""
        self.tail = [p for p in parts[2:] if len(p) >= 4]
        self.gender = _gender_from_name(parts)

    @property
    def ok(self) -> bool:
        return bool(self.id and self.surname)


def _surname_rank(token: str, card: _Card, blocked: set[str]) -> str | None:
    if token == card.surname and len(card.surname) >= 4:
        return "exact"
    if token in blocked or token in _STOP or _relative_form(token, card.surname):
        return None
    if len(token) < 6 or len(card.surname) < 6:
        return None
    dist = _lev(token, card.surname)
    if dist == 1:
        return "d1"
    if dist == 2 and len(token) >= 7 and len(card.surname) >= 7:
        return "d2"
    return None


def _given_points(token: str, card: _Card) -> int:
    if not card.given:
        return 0
    if token == card.given and len(card.given) >= 3:
        return 30
    if len(token) >= 4 and len(card.given) >= 4 and _lev(token, card.given) == 1:
        return 18
    return 0


def match_client(text: str, clients: list[dict]) -> str | None:
    """id клиента или None, если имя не узнали или оно неоднозначно."""
    cards = [c for raw in clients if (c := _Card(raw)).ok]
    if not cards or not (text or "").strip():
        return None
    toks = _tokens(text)
    words = {t for t, _ in toks}
    blocked = {c.given for c in cards if c.given} | {p for c in cards for p in c.tail}
    ranked: list[tuple[int, _Card, str, bool]] = []
    order = {"exact": 3, "d1": 2, "d2": 1}
    for card in cards:
        best: tuple[str, bool] | None = None
        for token, cap in toks:
            rank = _surname_rank(token, card, blocked)
            if rank and (best is None or order[rank] > order[best[0]]):
                best = (rank, cap)
        if best is None:
            continue
        score = {"exact": 50, "d1": 36, "d2": 30}[best[0]]
        how = best[0]
        given = max((_given_points(t, card) for t, _ in toks), default=0)
        if given:
            score += given
            how += "+given"
        if any(p in words for p in card.tail):
            score += 16
            how += "+pat"
        ranked.append((score, card, how, best[1]))
    if not ranked:
        return None
    ranked.sort(key=lambda item: -item[0])
    top_score = ranked[0][0]
    top = [item for item in ranked if item[0] == top_score]
    gender = _text_gender(words)
    if len(top) > 1 and gender:
        narrowed = [item for item in top if item[1].gender == gender]
        if len(narrowed) == 1:
            top = narrowed
    if len(top) != 1:
        return None
    score, card, how, capital = top[0]
    second = next((item[0] for item in ranked if item[1].id != card.id), 0)
    if second >= 48 and score - second < 15:
        return None
    same_surname = [c for c in cards if c.surname == card.surname]
    unique = len(same_surname) == 1
    same_gender = [c for c in same_surname if c.gender == card.gender]
    gender_hit = bool(gender and card.gender == gender and len(same_gender) == 1)
    if how.startswith("exact") and unique and score >= 50:
        return card.id
    if "+given" in how and score >= 64:
        return card.id
    if how.startswith("d1") and unique and (capital or gender_hit):
        return card.id
    if how.startswith("d2") and "+given" in how and score >= 64:
        return card.id
    if how.startswith("d2") and gender_hit:
        return card.id
    return None


def plan_auto_threads(messages: list[dict], clients: list[dict]) -> list[list[str]]:
    """Группы id: одна мысль, разрезанная на сообщения подряд.

    Берём только свободные сообщения (без нити и без ручного «не склеивать»).
    Следующее цепляется к предыдущему того же автора, если между ними не больше
    трёх минут и в нём самом нет имени клиента. Два разных клиента рядом не склеиваются.
    """
    free = [m for m in messages if not m.get("thread_id") and not m.get("thread_locked")]
    free.sort(key=lambda m: (str(m.get("author_key") or ""), m["created_at"]))
    groups: list[list[str]] = []
    bucket: list[dict] = []

    def flush() -> None:
        nonlocal bucket
        if len(bucket) >= 2:
            groups.append([str(m["id"]) for m in bucket])
        bucket = []

    for msg in free:
        if bucket:
            prev = bucket[-1]
            gap = (msg["created_at"] - prev["created_at"]).total_seconds()
            same_author = msg.get("author_key") == prev.get("author_key")
            names_someone = match_client(str(msg.get("text") or ""), clients) is not None
            if same_author and 0 <= gap <= CONTINUE_WITHIN.total_seconds() and not names_someone:
                bucket.append(msg)
                continue
            flush()
        bucket = [msg]
    flush()
    return groups
