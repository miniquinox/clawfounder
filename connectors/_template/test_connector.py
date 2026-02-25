"""
Template connector tests — copy and adapt for your connector.
"""

import pytest
from connector import TOOLS, handle


class TestToolDefinitions:
    """Validate that tool definitions follow the connector contract."""

    def test_tools_is_list(self):
        assert isinstance(TOOLS, list), "TOOLS must be a list"

    def test_tools_not_empty(self):
        assert len(TOOLS) > 0, "TOOLS must have at least one tool"

    def test_each_tool_has_required_fields(self):
        for tool in TOOLS:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool missing 'description': {tool}"
            assert "parameters" in tool, f"Tool missing 'parameters': {tool}"

    def test_tool_names_are_strings(self):
        for tool in TOOLS:
            assert isinstance(tool["name"], str), f"Tool name must be a string: {tool['name']}"

    def test_tool_names_are_snake_case(self):
        for tool in TOOLS:
            name = tool["name"]
            assert name == name.lower(), f"Tool name must be lowercase: {name}"
            assert " " not in name, f"Tool name must not have spaces: {name}"


class TestHandle:
    """Validate the handle() function."""

    def test_handle_is_callable(self):
        assert callable(handle), "handle must be a callable function"

    def test_handle_unknown_tool(self):
        result = handle("nonexistent_tool_xyz", {})
        assert isinstance(result, str), "handle() must return a string"

    def test_handle_returns_string(self):
        for tool in TOOLS:
            result = handle(tool["name"], {})
            assert isinstance(result, str), f"handle({tool['name']}) must return a string"
