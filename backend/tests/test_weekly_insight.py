"""Недельный отчёт: разбор названий, расчёт на синтетике, расписание и MCP — без сети и базы."""

from __future__ import annotations

import unittest
import uuid
from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from app.mcp_procurement.registry import ToolArgumentError, ToolPermissionError, get_tool, list_tools
from app.mcp_procurement.server import handle_message
from app.services.mcp_keys import McpActor
from app.services.weekly_insight.compute import Periods, build_report, sales_block, season_bounds
from app.services.warehouse_analytics.ms_client import MoySkladAnalyticsError
from app.services.weekly_insight.fetch import Dataset, MsFetcher, href_id
from app.services.weekly_insight.parse import arrival_month, category_of, season_of, size_of
from app.services.weekly_insight.runner import scheduled_due

TZ = ZoneInfo("Europe/Moscow")
RUN_DAY = date(2026, 10, 27)


def _actor(role: str = "superuser") -> McpActor:
    return McpActor(key_id=uuid.uuid4(), owner_role=role, user_id=None if role == "superuser" else uuid.uuid4(), scope="read")


def _line(day: str, agent: str, pid: str, vkey: str, total: float, *, list_price: float = 20000, discount: float = 10, check: str | None = None) -> dict:
    return {
        "check_id": check or f"{day}-{agent}-{vkey}",
        "day": day,
        "agent_id": agent,
        "agent_name": f"Клиент {agent}",
        "agent_phone": "+79000000000",
        "product_id": pid,
        "variant_key": vkey,
        "variant_name": f"{pid} (ВЛ2026, 50)",
        "size": "50",
        "qty": 1.0,
        "list_price": list_price,
        "discount_pct": discount,
        "sum": total,
    }


def _dataset() -> Dataset:
    catalog = {
        "p1": {"name": "A1/04.26 рубашка", "article": "A1/04.26", "path": "Мужская коллекция/Рубашки муж", "top": "Мужская коллекция", "gender": "M", "category": "Рубашки, блузки", "brand": "BRAND"},
        "p2": {"name": "A2/04.26 рубашка", "article": "A2/04.26", "path": "Мужская коллекция/Рубашки муж", "top": "Мужская коллекция", "gender": "M", "category": "Рубашки, блузки", "brand": "BRAND"},
    }
    sales = []
    # Постоянный клиент a: каждые 14 дней до июня, потом пропал — должен попасть в список на контроле.
    for k in range(20):
        d = date(2025, 11, 1).toordinal() + 14 * k
        sales.append(_line(date.fromordinal(d).isoformat(), "a", "p1", "v1", 300000))
    sales.append(_line("2026-10-20", "b", "p1", "v1", 18000))
    sales.append(_line("2026-10-21", "c", "p1", "v1", 10000, discount=50))
    sales.append(_line("2026-10-14", "c", "p1", "v1", 18000))
    arrivals = [
        {"day": "2025-10-01", "variant_key": "v1", "variant_name": "A1 (ВЛ2026, 50)", "product_id": "p1", "size": "50", "qty": 30.0, "cost": 5000.0},
        {"day": "2026-04-10", "variant_key": "v2", "variant_name": "A2 (ВЛ2026, 50)", "product_id": "p2", "size": "50", "qty": 3.0, "cost": 6000.0},
    ]
    stock = [{"variant_key": "v2", "name": "A2/04.26 рубашка (ВЛ2026, 50)", "product_id": "p2", "size": "50", "stock": 3.0, "cost": 6000.0, "sale_price": 21000.0}]
    return Dataset(
        catalog=catalog,
        sales=sales,
        arrivals=arrivals,
        stock=stock,
        profit={"cur": {"cogs": 100000.0, "revenue": 200000.0}, "prev": {"cogs": 90000.0, "revenue": 180000.0}},
    )


class ParseTests(unittest.TestCase):
    def test_category_and_size(self):
        self.assertEqual(category_of("Онлайн/Брюки/джинсы муж"), "Брюки, джинсы")
        self.assertEqual(size_of("ART рубашка (ОЗ2024, 44)"), "44")
        self.assertEqual(size_of("x", [{"name": "Размер", "value": "XL"}]), "XL")

    def test_arrival_and_season(self):
        self.assertEqual(arrival_month("87018-3/501/12.25", None, RUN_DAY), date(2025, 12, 1))
        self.assertIsNone(arrival_month("87018-3/501/12.27", None, RUN_DAY))
        self.assertEqual(season_of("x (ОЗ2027, 50)", date(2026, 8, 1)), "ОЗ2026")
        self.assertEqual(season_of("без сезона", date(2025, 12, 5)), "ВЛ2026")

    def test_href_id(self):
        obj = {"meta": {"href": "https://api.moysklad.ru/api/remap/1.2/entity/variant/1d4d5f44-7bb1-11e9-9109-f8fc00054224"}}
        self.assertEqual(href_id(obj), ("variant", "1d4d5f44-7bb1-11e9-9109-f8fc00054224"))


class FetchRetryTests(unittest.TestCase):
    def test_timeout_retried_then_reported_with_path(self):
        client = MagicMock()
        client.get.side_effect = [MoySkladAnalyticsError("Сеть МойСклад: Read timed out"), {"rows": []}]
        f = MsFetcher(client)
        with patch("app.services.weekly_insight.fetch.time.sleep"):
            self.assertEqual(f._get("/report/profit/byproduct", {}), {"rows": []})
            client.get.side_effect = MoySkladAnalyticsError("Сеть МойСклад: Read timed out")
            with self.assertRaises(MoySkladAnalyticsError) as ctx:
                f._get("/report/profit/byproduct", {"offset": 1000})
        self.assertIn("/report/profit/byproduct offset=1000", str(ctx.exception))

    def test_client_error_not_retried(self):
        client = MagicMock()
        client.get.side_effect = MoySkladAnalyticsError("HTTP 400", status=400)
        with patch("app.services.weekly_insight.fetch.time.sleep"), self.assertRaises(MoySkladAnalyticsError):
            MsFetcher(client)._get("/entity/product", {})
        self.assertEqual(client.get.call_count, 1)


class ComputeTests(unittest.TestCase):
    def test_periods_take_previous_full_week(self):
        for run in (date(2026, 10, 26), RUN_DAY, date(2026, 11, 1)):
            p = Periods.for_run(run)
            self.assertEqual((p.week_start, p.week_end), (date(2026, 10, 19), date(2026, 10, 25)))

    def test_season_bounds(self):
        self.assertEqual(season_bounds(date(2026, 10, 25)), (date(2026, 8, 1), "ОЗ2026"))
        self.assertEqual(season_bounds(date(2027, 1, 10)), (date(2026, 8, 1), "ОЗ2026"))
        self.assertEqual(season_bounds(date(2027, 3, 1)), (date(2027, 2, 1), "ВЛ2027"))

    def test_season_compares_same_dates_last_year(self):
        metrics, _ = build_report(_dataset(), RUN_DAY, procurement={"season": "ОЗ26-27", "to_ship_eur": 0})
        season = metrics["season"]
        self.assertEqual(season["period"], {"from": "2026-08-01", "to": "2026-10-25"})
        self.assertEqual(season["period_last_year"], {"from": "2025-08-01", "to": "2025-10-25"})
        self.assertEqual(season["sales"]["revenue"], 18000 + 10000 + 18000)
        self.assertEqual(metrics["procurement"]["season"], "ОЗ26-27")

    def test_sales_block_splits_card_and_markdown(self):
        blk = sales_block([_line("2026-10-20", "x", "p1", "v1", 18000), _line("2026-10-20", "x", "p1", "v1", 10000, discount=50)])
        self.assertEqual(blk["revenue"], 28000)
        self.assertEqual(blk["markdown_units_pct"], 50.0)
        self.assertEqual(blk["avg_discount_pct"], 30.0)

    def test_report_week_clients_and_watchlist(self):
        metrics, watch = build_report(_dataset(), RUN_DAY, prev_watchlist_ids={"b"}, staff_feedback={"messages_week": 0})
        week = metrics["week"]
        self.assertEqual(week["sales"]["revenue"], 28000)
        self.assertEqual(week["buyers_named"], 2)
        self.assertEqual(week["buyers_new"], 1)
        self.assertEqual(week["returned_from_prev_watchlist"], {"clients": 1, "revenue": 18000, "watchlist_size": 1})
        self.assertEqual(len(metrics["dynamics"]), 13)
        self.assertEqual(metrics["overall"]["months_of_stock"], round(18000 / (100000 / 12), 1))

        self.assertEqual([w["id"] for w in watch], ["a"])
        self.assertEqual(watch[0]["status"], "просрочил визит")
        self.assertEqual([p["name"] for p in watch[0]["picks"]], ["A2/04.26 рубашка (ВЛ2026, 50)"])
        self.assertNotIn("Клиент a", str(metrics))
        self.assertTrue(any("«Спрос»" in s for s in metrics["suggestions"]))


class ScheduleTests(unittest.TestCase):
    def _settings(self):
        return SimpleNamespace(weekly_insight_enabled=True, moysklad_configured=True, weekly_insight_hour=7)

    def _db(self, rows):
        db = MagicMock()
        db.scalars.return_value.all.return_value = rows
        return db

    def test_waits_until_monday_hour(self):
        self.assertFalse(scheduled_due(self._db([]), self._settings(), datetime(2026, 10, 26, 6, 30, tzinfo=TZ)))
        self.assertTrue(scheduled_due(self._db([]), self._settings(), datetime(2026, 10, 26, 7, 5, tzinfo=TZ)))

    def test_catches_up_later_in_week_but_not_twice(self):
        self.assertTrue(scheduled_due(self._db([]), self._settings(), datetime(2026, 10, 28, 3, 0, tzinfo=TZ)))
        done = SimpleNamespace(status="done", trigger="manual")
        self.assertFalse(scheduled_due(self._db([done]), self._settings(), datetime(2026, 10, 28, 3, 0, tzinfo=TZ)))
        errors = [SimpleNamespace(status="error", trigger="schedule")] * 3
        self.assertFalse(scheduled_due(self._db(errors), self._settings(), datetime(2026, 10, 28, 3, 0, tzinfo=TZ)))


class WeeklyInsightMcpTests(unittest.TestCase):
    def test_tools_listed_and_described(self):
        names = [item["name"] for item in list_tools("read")]
        self.assertIn("list_weekly_reports", names)
        self.assertIn("get_weekly_report", names)
        response = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}, MagicMock(), _actor())
        self.assertIn("get_weekly_report", response["result"]["instructions"])

    def test_worker_key_rejected(self):
        with self.assertRaises(ToolPermissionError):
            get_tool("list_weekly_reports").handler(MagicMock(), _actor("worker"))
        with self.assertRaises(ToolPermissionError):
            get_tool("get_weekly_report").handler(MagicMock(), _actor("worker"))

    def test_bad_arguments_rejected(self):
        tool = get_tool("get_weekly_report")
        with self.assertRaises(ToolArgumentError):
            tool.handler(MagicMock(), _actor(), detail="всё")
        with self.assertRaises(ToolArgumentError):
            tool.handler(MagicMock(), _actor(), report_id="нет")
