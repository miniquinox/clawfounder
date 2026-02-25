"""Firebase connector tests."""

import pytest
from connector import TOOLS, handle


class TestToolDefinitions:
    def test_tools_is_list(self):
        assert isinstance(TOOLS, list)

    def test_has_expected_tools(self):
        names = [t["name"] for t in TOOLS]
        assert "firebase_get_document" in names
        assert "firebase_list_collection" in names
        assert "firebase_set_document" in names

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

    def test_handle_returns_string_on_error(self):
        result = handle("firebase_get_document", {"path": "test/doc"})
        assert isinstance(result, str)
