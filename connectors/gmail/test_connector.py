"""Gmail connector tests."""

import pytest
from unittest.mock import patch, MagicMock
from connector import TOOLS, handle


class TestToolDefinitions:
    def test_tools_is_list(self):
        assert isinstance(TOOLS, list)

    def test_tools_not_empty(self):
        assert len(TOOLS) > 0

    def test_has_get_unread(self):
        names = [t["name"] for t in TOOLS]
        assert "gmail_get_unread" in names

    def test_has_search(self):
        names = [t["name"] for t in TOOLS]
        assert "gmail_search" in names

    def test_has_send(self):
        names = [t["name"] for t in TOOLS]
        assert "gmail_send" in names

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

    @patch("connector._get_gmail_service")
    def test_get_unread_no_messages(self, mock_service):
        mock_svc = MagicMock()
        mock_svc.users().messages().list().execute.return_value = {"messages": []}
        mock_service.return_value = mock_svc
        result = handle("gmail_get_unread", {})
        assert isinstance(result, str)

    def test_handle_returns_string_on_error(self):
        # Without credentials, it should return an error string, not crash
        result = handle("gmail_get_unread", {})
        assert isinstance(result, str)
