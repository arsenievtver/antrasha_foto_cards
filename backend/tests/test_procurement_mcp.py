"""MCP закупок: протокол и границы инструментов, без базы."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock

from app.mcp_procurement.registry import get_tool, list_tools
from app.mcp_procurement.server import handle_message
from app.services.mcp_keys import McpActor, hash_key


def _actor(scope: str) -> McpActor:
    return McpActor(
        key_id=uuid.uuid4(),
        owner_role="superuser",
        user_id=None,
        scope=scope,
    )


class ProcurementMcpProtocolTests(unittest.TestCase):
    def test_initialize_names_this_server(self):
        response = handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            MagicMock(),
            _actor("read"),
        )
        info = response["result"]["serverInfo"]
        self.assertEqual(info["name"], "antrasha-procurement")
        self.assertIn("Удаления нет", response["result"]["instructions"])

    def test_read_key_does_not_see_writes_or_deletes(self):
        names = [item["name"] for item in list_tools("read")]
        self.assertIn("list_seasons", names)
        self.assertIn("list_brand_orders", names)
        self.assertIn("list_fx_rates", names)
        self.assertNotIn("create_season", names)
        self.assertNotIn("update_payment", names)
        self.assertFalse(any("delete" in name for name in names))

    def test_write_key_can_change_but_not_delete(self):
        names = [item["name"] for item in list_tools("write")]
        for required in (
            "create_season",
            "update_season",
            "create_brand",
            "update_brand",
            "create_brand_order",
            "update_brand_order",
            "create_payment",
            "update_payment",
            "create_shipment",
            "update_shipment",
            "create_fx_rate",
            "update_fx_rate",
        ):
            self.assertIn(required, names)
        self.assertFalse(any("delete" in name for name in names))
        self.assertIsNone(get_tool("delete_season"))
        self.assertIsNone(get_tool("delete_brand"))
        self.assertIsNone(get_tool("delete_payment"))

    def test_read_key_cannot_call_a_write_tool(self):
        response = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "create_season",
                    "arguments": {"name": "Весна", "code": "ВЛ"},
                },
            },
            MagicMock(),
            _actor("read"),
        )
        content = response["result"]
        self.assertTrue(content["isError"])
        self.assertIn("правом записи", content["content"][0]["text"])

    def test_unknown_argument_is_a_tool_error(self):
        response = handle_message(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "create_brand",
                    "arguments": {"name": "Transit", "extra": 1},
                },
            },
            MagicMock(),
            _actor("write"),
        )
        self.assertTrue(response["result"]["isError"])
        self.assertIn("Неизвестные аргументы", response["result"]["content"][0]["text"])

    def test_key_hash_is_stable(self):
        self.assertEqual(hash_key("mcp_live_abc"), hash_key("mcp_live_abc"))
        self.assertNotEqual(hash_key("mcp_live_abc"), hash_key("mcp_live_abd"))


if __name__ == "__main__":
    unittest.main()
