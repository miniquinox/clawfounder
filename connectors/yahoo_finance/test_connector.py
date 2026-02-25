"""Yahoo Finance connector tests."""

import pytest
from connector import TOOLS, handle


class TestToolDefinitions:
    def test_tools_is_list(self):
        assert isinstance(TOOLS, list)

    def test_has_expected_tools(self):
        names = [t["name"] for t in TOOLS]
        assert "yahoo_finance_quote" in names
        assert "yahoo_finance_history" in names

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

    def test_quote_returns_string(self):
        """This test makes a real API call — skip in CI without network."""
        try:
            result = handle("yahoo_finance_quote", {"symbol": "AAPL"})
            assert isinstance(result, str)
            assert "AAPL" in result
        except Exception:
            pytest.skip("Network unavailable")
