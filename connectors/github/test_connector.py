"""GitHub connector tests."""

import pytest
from connector import TOOLS, handle


class TestToolDefinitions:
    def test_tools_is_list(self):
        assert isinstance(TOOLS, list)

    def test_has_expected_tools(self):
        names = [t["name"] for t in TOOLS]
        assert "github_list_repos" in names
        assert "github_get_commits" in names
        assert "github_list_issues" in names
        assert "github_create_issue" in names

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
        result = handle("github_list_repos", {})
        assert isinstance(result, str)
