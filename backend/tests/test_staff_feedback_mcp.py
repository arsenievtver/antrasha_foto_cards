"""MCP раздела «Спрос»: регистрация и проверка аргументов, без базы."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock

from app.deps import AdminPrincipal
from app.mcp_procurement.registry import (
    ToolArgumentError,
    ToolPermissionError,
    get_tool,
    list_tools,
)
from app.mcp_procurement.server import handle_message
from app.models.staff_feedback import StaffFeedback
from app.services.mcp_keys import McpActor
from app.services.staff_feedback import SUPERUSER_LABEL, is_own


def _actor() -> McpActor:
    return McpActor(
        key_id=uuid.uuid4(),
        owner_role="superuser",
        user_id=None,
        scope="read",
    )


class StaffFeedbackMcpTests(unittest.TestCase):
    def test_read_key_sees_feedback_tools(self):
        names = [item["name"] for item in list_tools("read")]
        self.assertIn("list_staff_feedback", names)
        self.assertIn("get_staff_feedback_stats", names)

    def test_initialize_mentions_feedback(self):
        response = handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            MagicMock(),
            _actor(),
        )
        self.assertIn("list_staff_feedback", response["result"]["instructions"])
        self.assertIn("list_app_users", response["result"]["instructions"])

    def test_bad_date_rejected(self):
        tool = get_tool("get_staff_feedback_stats")
        with self.assertRaises(ToolArgumentError):
            tool.handler(MagicMock(), _actor(), date_from="30.09.2026")

    def test_worker_key_rejected(self):
        actor = McpActor(
            key_id=uuid.uuid4(), owner_role="worker", user_id=uuid.uuid4(), scope="read"
        )
        with self.assertRaises(ToolPermissionError):
            get_tool("list_staff_feedback").handler(MagicMock(), actor)
        with self.assertRaises(ToolPermissionError):
            get_tool("get_staff_feedback_stats").handler(MagicMock(), actor)

    def test_bad_author_rejected(self):
        tool = get_tool("list_staff_feedback")
        with self.assertRaises(ToolArgumentError):
            tool.handler(MagicMock(), _actor(), author_user_id="нет")


class StaffFeedbackOwnershipTests(unittest.TestCase):
    def test_worker_owns_only_own_rows(self):
        user = MagicMock(id=uuid.uuid4(), display_name="Аня", phone="+7900")
        principal = AdminPrincipal(role="worker", user=user)
        mine = StaffFeedback(author_user_id=user.id, author_label="Аня", text="x")
        other = StaffFeedback(author_user_id=uuid.uuid4(), author_label="Оля", text="y")
        self.assertTrue(is_own(mine, principal))
        self.assertFalse(is_own(other, principal))

    def test_superuser_does_not_own_deleted_worker_rows(self):
        principal = AdminPrincipal(role="superuser", user=None)
        own = StaffFeedback(author_user_id=None, author_label=SUPERUSER_LABEL, text="x")
        orphan = StaffFeedback(author_user_id=None, author_label="Удалённая Оля", text="y")
        self.assertTrue(is_own(own, principal))
        self.assertFalse(is_own(orphan, principal))
