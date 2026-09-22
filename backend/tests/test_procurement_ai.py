"""Агент закупок: скоуп ключа и правила промпта, без Anthropic."""

from __future__ import annotations

import unittest

from app.services.procurement_ai import (
    SCOPE_READ,
    anthropic_tools,
    effective_scope,
    system_prompt,
)


class ProcurementAiScopeTests(unittest.TestCase):
    def test_write_key_is_the_only_write_scope(self):
        self.assertEqual(effective_scope("write"), "write")
        self.assertEqual(effective_scope("read"), SCOPE_READ)
        self.assertEqual(effective_scope(None), SCOPE_READ)

    def test_read_tools_cannot_change_data(self):
        names = [item["name"] for item in anthropic_tools("read")]
        self.assertIn("list_shipments", names)
        self.assertIn("get_season_dashboard", names)
        self.assertNotIn("create_shipment", names)
        self.assertNotIn("update_payment", names)
        self.assertFalse(any("delete" in name for name in names))

    def test_write_tools_include_records_but_not_delete(self):
        names = [item["name"] for item in anthropic_tools("write")]
        self.assertIn("create_shipment", names)
        self.assertIn("update_brand_order", names)
        self.assertIn("list_shipments", names)
        self.assertFalse(any("delete" in name for name in names))
        self.assertTrue(all("input_schema" in item for item in anthropic_tools("write")))

    def test_prompt_asks_before_write_and_describes_charts(self):
        text = system_prompt(can_write=True)
        self.assertIn("не вызывай инструмент", text)
        self.assertIn("```chart", text)
        self.assertIn("Удалять нельзя", text)
        self.assertIn("МойСклад", text)
        read_only = system_prompt(can_write=False)
        self.assertIn("только чтение", read_only)


if __name__ == "__main__":
    unittest.main()
