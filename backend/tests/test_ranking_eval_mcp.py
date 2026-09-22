"""MCP оценки ранжирования: регистрация и сводка эмбеддингов, без базы."""

from __future__ import annotations

import unittest
import uuid
from unittest.mock import MagicMock

from app.mcp_procurement.registry import ToolArgumentError, get_tool, list_tools
from app.mcp_procurement.server import handle_message
from app.services.mcp_keys import McpActor
from app.services.ranking_eval_inspect import embedding_spread


def _actor() -> McpActor:
    return McpActor(
        key_id=uuid.uuid4(),
        owner_role="superuser",
        user_id=None,
        scope="read",
    )


class RankingEvalMcpTests(unittest.TestCase):
    def test_read_key_sees_ranking_eval_tools(self):
        names = [item["name"] for item in list_tools("read")]
        self.assertIn("list_ranking_eval_submissions", names)
        self.assertIn("get_ranking_eval_submission", names)

    def test_initialize_mentions_ranking_eval(self):
        response = handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            MagicMock(),
            _actor(),
        )
        self.assertIn("get_ranking_eval_submission", response["result"]["instructions"])

    def test_detail_requires_uuid(self):
        tool = get_tool("get_ranking_eval_submission")
        self.assertIsNotNone(tool)
        with self.assertRaises(ToolArgumentError):
            tool.handler(MagicMock(), _actor(), submission_id="нет")

    def test_identical_photos_have_cosine_one(self):
        spread = embedding_spread([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
        self.assertEqual(spread["pairs"], 3)
        self.assertEqual(spread["max"], 1.0)
        self.assertEqual(spread["min"], 0.0)
