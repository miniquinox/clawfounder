"""Telegram connector tests."""

import pytest
from unittest.mock import patch, MagicMock
from connector import TOOLS, handle


class TestToolDefinitions:
    def test_tools_is_list(self):
        assert isinstance(TOOLS, list)

    def test_has_send_message(self):
        assert "telegram_send_message" in [t["name"] for t in TOOLS]

    def test_has_get_updates(self):
        assert "telegram_get_updates" in [t["name"] for t in TOOLS]

    def test_each_tool_has_required_fields(self):
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool


class TestHandle:
    def test_handle_is_callable(self):
        assert callable(handle)

    def test_handle_unknown_tool(self):
        result = handle("nonexistent_tool", {})
        assert isinstance(result, str)

    @patch("connector.requests.post")
    @patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "fake", "TELEGRAM_CHAT_ID": "123"})
    def test_send_message_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)
        result = handle("telegram_send_message", {"text": "hello"})
        assert isinstance(result, str)
        assert "sent" in result.lower() or "message" in result.lower()

    def test_send_message_no_token(self):
        result = handle("telegram_send_message", {"text": "hello"})
        assert isinstance(result, str)
