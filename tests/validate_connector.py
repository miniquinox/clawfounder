"""
validate_connector.py — Structural validator for ClawFounder connectors.

Checks that a connector folder has all required files and follows the contract.

Usage:
    python tests/validate_connector.py connectors/gmail
    python tests/validate_connector.py connectors/your_service
"""

import sys
import os
import importlib.util
from pathlib import Path

REQUIRED_FILES = [
    "instructions.md",
    "connector.py",
    "requirements.txt",
    "install.sh",
    "test_connector.py",
]

REQUIRED_TOOL_FIELDS = ["name", "description", "parameters"]


def validate(connector_path: str) -> tuple[bool, list[str]]:
    """
    Validate a connector directory.

    Returns:
        (passed: bool, messages: list[str])
    """
    errors = []
    warnings = []
    path = Path(connector_path)

    if not path.exists():
        return False, [f"❌ Path does not exist: {connector_path}"]

    if not path.is_dir():
        return False, [f"❌ Not a directory: {connector_path}"]

    connector_name = path.name

    # ── Check required files ──────────────────────────────────────
    for filename in REQUIRED_FILES:
        filepath = path / filename
        if not filepath.exists():
            errors.append(f"❌ Missing file: {filename}")
        else:
            # Check it's not empty
            if filepath.stat().st_size == 0:
                warnings.append(f"⚠️  Empty file: {filename}")

    # ── Check connector.py contract ───────────────────────────────
    connector_file = path / "connector.py"
    if connector_file.exists():
        try:
            spec = importlib.util.spec_from_file_location(
                f"validate.{connector_name}", str(connector_file)
            )
            module = importlib.util.module_from_spec(spec)

            old_path = sys.path.copy()
            sys.path.insert(0, str(path))
            spec.loader.exec_module(module)
            sys.path = old_path

            # Check TOOLS
            if not hasattr(module, "TOOLS"):
                errors.append("❌ connector.py missing TOOLS list")
            elif not isinstance(module.TOOLS, list):
                errors.append("❌ TOOLS is not a list")
            elif len(module.TOOLS) == 0:
                errors.append("❌ TOOLS list is empty")
            else:
                for i, tool in enumerate(module.TOOLS):
                    for field in REQUIRED_TOOL_FIELDS:
                        if field not in tool:
                            errors.append(f"❌ Tool #{i} missing '{field}' field")

                    if "name" in tool:
                        name = tool["name"]
                        if name != name.lower():
                            warnings.append(f"⚠️  Tool name should be lowercase: {name}")
                        if " " in name:
                            errors.append(f"❌ Tool name must not contain spaces: {name}")

            # Check handle
            if not hasattr(module, "handle"):
                errors.append("❌ connector.py missing handle() function")
            elif not callable(module.handle):
                errors.append("❌ handle is not callable")
            else:
                # Test that handle returns a string for unknown tools
                try:
                    result = module.handle("__validate_unknown_tool__", {})
                    if not isinstance(result, str):
                        errors.append("❌ handle() must return a string")
                except Exception as e:
                    errors.append(f"❌ handle() crashed on unknown tool: {e}")

        except Exception as e:
            errors.append(f"❌ Failed to import connector.py: {e}")

    # ── Check install.sh is executable-like ───────────────────────
    install_file = path / "install.sh"
    if install_file.exists():
        content = install_file.read_text()
        if not content.strip().startswith("#!/"):
            warnings.append("⚠️  install.sh missing shebang (#!/bin/bash)")

    messages = errors + warnings
    passed = len(errors) == 0
    return passed, messages


def main():
    if len(sys.argv) < 2:
        print("Usage: python tests/validate_connector.py <connector_path>")
        print("Example: python tests/validate_connector.py connectors/gmail")
        sys.exit(1)

    connector_path = sys.argv[1]
    connector_name = Path(connector_path).name

    print(f"\n🔍 Validating connector: {connector_name}")
    print("─" * 50)

    passed, messages = validate(connector_path)

    for msg in messages:
        print(f"  {msg}")

    print("─" * 50)
    if passed:
        if messages:
            print(f"✅ {connector_name} passed with warnings")
        else:
            print(f"✅ {connector_name} passed all checks!")
    else:
        print(f"❌ {connector_name} failed validation")
    print()

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
