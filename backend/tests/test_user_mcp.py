"""MCP пользователей приложения: регистрация инструментов и права."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock

from app.mcp_procurement.registry import ToolPermissionError, get_tool, list_tools
from app.services.mcp_keys import McpActor


def _superuser_read() -> McpActor:
    return McpActor(
        key_id=uuid.uuid4(),
        owner_role="superuser",
        user_id=None,
        scope="read",
    )


def _worker_read() -> McpActor:
    return McpActor(
        key_id=uuid.uuid4(),
        owner_role="worker",
        user_id=uuid.uuid4(),
        scope="read",
    )


class AppUserMcpTests(unittest.TestCase):
    def test_read_catalog_includes_user_tools(self):
        names = [item["name"] for item in list_tools("read")]
        self.assertIn("get_app_user", names)
        self.assertIn("list_fitting_requests", names)

    def test_worker_key_cannot_list_app_users(self):
        tool = get_tool("list_app_users")
        assert tool is not None
        with self.assertRaises(ToolPermissionError):
            tool.handler(MagicMock(), _worker_read())

    def test_get_app_user_requires_identifier(self):
        tool = get_tool("get_app_user")
        assert tool is not None
        from app.mcp_procurement.registry import ToolArgumentError

        with self.assertRaises(ToolArgumentError):
            tool.handler(MagicMock(), _superuser_read())


if __name__ == "__main__":
    unittest.main()
