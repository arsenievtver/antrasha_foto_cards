"""Разбор комментариев «Спроса» по клиентам А: без базы."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from app.mcp_procurement.registry import ToolArgumentError, ToolPermissionError, get_tool, list_tools
from app.services.a_client_match import match_client, plan_auto_threads
from app.services.mcp_keys import McpActor

import app.mcp_procurement.a_client_tools  # noqa: F401,E402
import app.mcp_procurement.staff_feedback_tools  # noqa: F401,E402

CLIENTS = [
    {"id": "denisov", "name": "Денисов Алексей Николаевич"},
    {"id": "derevcev", "name": "Деревцев Сергей Анатольевич"},
    {"id": "kirsanov", "name": "Кирсанов Владимир Владимирович"},
    {"id": "kersanova", "name": "Керсанова Татьяна Борисовна"},
    {"id": "timofeev", "name": "Тимофеев Юрий Васильевич"},
    {"id": "seker", "name": "Секержицкий Антон Мечиславович"},
    {"id": "mishin", "name": "Мишин Андрей Валентинович"},
    {"id": "ivanov-k", "name": "Иванов Константин Николаевич"},
    {"id": "ivanov-s", "name": "Иванов Сергей Константинович"},
    {"id": "ivanova", "name": "Иванова Ирина Игоревна"},
    {"id": "isaev", "name": "Исаев Адлан Магомедович"},
    {"id": "bud-f", "name": "Будылко Наталья Павловна"},
    {"id": "bud-m", "name": "Будылко Виктор Павлович"},
    {"id": "petrova-e", "name": "Петрова Елена Викторовна"},
    {"id": "petrova-y", "name": "Петрова Юлия Сергеевна"},
    {"id": "ibragimova", "name": "Ибрагимова Арифа Ариф Кызы"},
    {"id": "krylova", "name": "Крылова Алефтина Михайловна"},
    {"id": "dremacheva", "name": "Дремачева Светлана Геннадьевна"},
    {"id": "ingvar", "name": "Ингвар Игорь Иванович"},
    {"id": "muha", "name": "Мухамеджанов Дмитрий Зингорович"},
    {"id": "gordeev", "name": "Гордеев Роман Николаевич"},
    {"id": "shologon", "name": "Шологон Василий Прокопович"},
    {"id": "kargin", "name": "Каргин Евгений Олегович"},
    {"id": "nikolaeva", "name": "Николаева Галина Викторовна"},
    {"id": "kozlov", "name": "Козлов Дмитрий Юрьевич"},
    {"id": "samarina", "name": "Самарина Лада Геннадьевна"},
    {"id": "kogan", "name": "Коган Михаил Яковлевич"},
    {"id": "piskarev", "name": "Пискарев Сергей Владимирович"},
    {"id": "sharifov", "name": "Шарифов Айваз Иса Оглы"},
    {"id": "martirosyan", "name": "Мартиросян Вреж Коляевич"},
    {"id": "mkrtchyan", "name": "Мкртчян Вардан Арутюнович"},
    {"id": "andreev", "name": "Андреев Роман Сергеевич"},
]

# Реальные тексты из «Спроса» и ожидаемый клиент.
CASES = [
    ("Совершенно нет больших размеров в женском зале", None),
    ("Женских пальто 42 размера в продаже нет", None),
    ("Был Комаров просил серые джинсы и кардиганы", None),
    ("Сказал нужно переспать подумать и ушел", None),
    ("Иванов", None),
    ("Ибрагимова Арифа Ариф Кызы, последний раз созванивались", "ibragimova"),
    ("Ингвар Игорь Иванович, перестали держать связь", "ingvar"),
    ("Мухамеджанов Дмитрий Зингорович, держим связь", "muha"),
    ("Коган Михаил всегда заходит мало покупает", "kogan"),
    ("Будылко Виктор Павлович, держим связь постоянно", "bud-m"),
    ("Пискарёв Сергей приходил в понедельник", "piskarev"),
    ("Шерифов Айваз Иса оглы  был недавно купил", "sharifov"),
    ("Исаев Адлан Магомедович, связь держим постоянно", "isaev"),
    ("Мартиросян врежь Калиевич был недавно взял на счёт", "martirosyan"),
    ("Мкртчян Вардан Арутюнович, приходит по случаю", "mkrtchyan"),
    ("Иванов Сергей Константинович в том году приходил", "ivanov-s"),
    ("Шологон Василий Прокопович переодически заходит", "shologon"),
    ("Каргин Евгений Олегович  перестал ходить", "kargin"),
    ("Гордеев Роман Николаевич, последний раз держали связь", "gordeev"),
    ("Тимофеев Юрий Васильевич, держим связь", "timofeev"),
    ("Николаева Галина Викторовна перестала ходить", "nikolaeva"),
    ("СЕКЕРЖИТСКИЙ Антон мечиславович, заходит всегда", "seker"),
    ("Козлов Дмитрий Юрьевич не приходит потому,что живет в Москве", "kozlov"),
    ("Мишин Андрей Валентинович, приглашали на новые колекции", "mishin"),
    ("Денисов Алексей Николаевич, держу с ним связь постоянно", "denisov"),
    ("Деревцев Сергей Анатольевич, приглашаю на новый Асортимент", "derevcev"),
    ("Самарина Лада Геннадьевна Кристина ей написала", "samarina"),
    ("Петрова Елена Викторовна ходит ждала брюки", "petrova-e"),
    ("Кирсанов Владимир Владимирович, последний раз был летом", "kirsanov"),
    ("Крылова Алевтина была четыре дня назад ничего не купила", "krylova"),
    ("Была Дремочева у Кристины как всегда взяла много вещей", "dremacheva"),
    ("Кристина звонила бутылка они уехали в Кисловодск ну последний раз когда приходила не было размеров размер у неё 50-й", "bud-f"),
    ("Кирсанова Татьяна живёт в Черногории приезжает только летом", "kersanova"),
]


def _actor() -> McpActor:
    return McpActor(key_id=uuid.uuid4(), owner_role="superuser", user_id=None, scope="read")


class MatchTests(unittest.TestCase):
    def test_real_comments_land_on_the_right_client(self):
        for text, expected in CASES:
            with self.subTest(text=text[:48]):
                self.assertEqual(match_client(text, CLIENTS), expected)

    def test_andrey_is_not_andreev(self):
        self.assertEqual(match_client("Мишин Андрей смотрел пиджак", CLIENTS), "mishin")

    def test_split_thought_merges_and_named_pair_does_not(self):
        start = datetime(2026, 11, 3, 9, 14, 42, tzinfo=timezone.utc)
        rows = [
            {"id": "a", "author_key": "katya", "created_at": start, "text": "Был Комаров просил серые джинсы", "thread_id": None, "thread_locked": False},
            {"id": "b", "author_key": "katya", "created_at": start + timedelta(seconds=20), "text": "Сказал нужно переспать подумать и ушел", "thread_id": None, "thread_locked": False},
            {"id": "c", "author_key": "katya", "created_at": start + timedelta(hours=24), "text": "Кирсанова Татьяна живёт в Черногории", "thread_id": None, "thread_locked": False},
            {"id": "d", "author_key": "katya", "created_at": start + timedelta(hours=24, minutes=2), "text": "Была Дремочева у Кристины", "thread_id": None, "thread_locked": False},
        ]
        self.assertEqual(plan_auto_threads(rows, CLIENTS), [["a", "b"]])

    def test_locked_message_is_left_alone(self):
        start = datetime(2026, 11, 3, 9, 14, tzinfo=timezone.utc)
        rows = [
            {"id": "a", "author_key": "katya", "created_at": start, "text": "Был Комаров", "thread_id": None, "thread_locked": True},
            {"id": "b", "author_key": "katya", "created_at": start + timedelta(seconds=20), "text": "Сказал нужно переспать", "thread_id": None, "thread_locked": False},
        ]
        self.assertEqual(plan_auto_threads(rows, CLIENTS), [])


class AClientMcpTests(unittest.TestCase):
    def test_read_key_sees_tools(self):
        names = [item["name"] for item in list_tools("read")]
        self.assertIn("list_a_clients", names)
        self.assertIn("get_a_client", names)
        self.assertIn("list_active_a_clients", names)
        self.assertNotIn("sync_a_clients", names)
        self.assertNotIn("merge_staff_feedback", names)

    def test_write_key_sees_changes(self):
        names = [item["name"] for item in list_tools("write")]
        for name in (
            "sync_a_clients",
            "add_a_client_caretaker",
            "dismiss_a_client_caretaker",
            "merge_staff_feedback",
            "split_staff_feedback",
            "set_staff_feedback_client",
        ):
            self.assertIn(name, names)

    def test_read_key_cannot_change(self):
        from app.mcp_procurement.registry import call_tool

        actor = McpActor(key_id=uuid.uuid4(), owner_role="superuser", user_id=None, scope="read")
        with self.assertRaises(ToolPermissionError):
            call_tool(get_tool("sync_a_clients"), object(), actor, {})
        with self.assertRaises(ToolPermissionError):
            call_tool(get_tool("merge_staff_feedback"), object(), actor, {"feedback_ids": []})

    def test_worker_key_rejected(self):
        actor = McpActor(key_id=uuid.uuid4(), owner_role="worker", user_id=uuid.uuid4(), scope="write")
        with self.assertRaises(ToolPermissionError):
            get_tool("list_a_clients").handler(object(), actor)
        with self.assertRaises(ToolPermissionError):
            get_tool("sync_a_clients").handler(object(), actor)

    def test_bad_id_rejected(self):
        with self.assertRaises(ToolArgumentError):
            get_tool("get_a_client").handler(object(), _actor(), client_id="нет")

    def test_merge_needs_two_real_ids(self):
        actor = McpActor(key_id=uuid.uuid4(), owner_role="superuser", user_id=None, scope="write")
        tool = get_tool("merge_staff_feedback")
        with self.assertRaises(ToolArgumentError):
            tool.handler(object(), actor, feedback_ids=["нет"])
        with self.assertRaises(ToolArgumentError):
            tool.handler(object(), actor, feedback_ids=[str(uuid.uuid4())])

    def test_bind_requires_client_argument(self):
        from app.mcp_procurement.registry import call_tool

        actor = McpActor(key_id=uuid.uuid4(), owner_role="superuser", user_id=None, scope="write")
        with self.assertRaises(ToolArgumentError):
            call_tool(get_tool("set_staff_feedback_client"), object(), actor, {"feedback_id": str(uuid.uuid4())})
