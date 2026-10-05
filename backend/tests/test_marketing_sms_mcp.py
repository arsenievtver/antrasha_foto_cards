"""MCP send_marketing_sms_batch: права и dry_run."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock, patch

from app.mcp_procurement.registry import ToolArgumentError, ToolPermissionError, get_tool
from app.services.mcp_keys import McpActor


def _superuser_write() -> McpActor:
    return McpActor(
        key_id=uuid.uuid4(),
        owner_role="superuser",
        user_id=None,
        scope="write",
    )


def _worker_write() -> McpActor:
    return McpActor(
        key_id=uuid.uuid4(),
        owner_role="worker",
        user_id=uuid.uuid4(),
        scope="write",
    )


class MarketingSmsMcpTests(unittest.TestCase):
    def test_worker_key_rejected(self):
        tool = get_tool("send_marketing_sms_batch")
        assert tool is not None
        with self.assertRaises(ToolPermissionError):
            tool.handler(
                MagicMock(),
                _worker_write(),
                text="hi",
                phones=["+79000000000"],
                dry_run=True,
            )

    @patch("app.mcp_procurement.gift_certificate_tools.deliver_marketing_sms_batch")
    def test_dry_run_delegates(self, mock_deliver: MagicMock):
        mock_deliver.return_value = {"sent_count": 1, "dry_run": True}
        tool = get_tool("send_marketing_sms_batch")
        assert tool is not None
        out = tool.handler(
            MagicMock(),
            _superuser_write(),
            text="Тест",
            phones=["+79106492742"],
            dry_run=True,
        )
        self.assertTrue(out["dry_run"])
        mock_deliver.assert_called_once()

    def test_empty_phones_rejected(self):
        tool = get_tool("send_marketing_sms_batch")
        assert tool is not None
        with self.assertRaises(ToolArgumentError):
            tool.handler(MagicMock(), _superuser_write(), text="x", phones=[])


if __name__ == "__main__":
    unittest.main()
