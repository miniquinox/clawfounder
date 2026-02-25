"""
connector_loader.py — Auto-discovers connectors from the connectors/ directory.

Scans each subfolder, imports connector.py, and collects TOOLS + handle functions.
"""

import os
import sys
import importlib.util
from pathlib import Path


def load_connectors(connectors_dir: str = None) -> dict:
    """
    Scan the connectors/ directory and load each connector.

    Returns a dict:
    {
        "connector_name": {
            "tools": [...],        # The TOOLS list from connector.py
            "handle": <function>,  # The handle() function
            "path": "/abs/path"    # Path to the connector folder
        }
    }
    """
    if connectors_dir is None:
        connectors_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "connectors")

    connectors = {}
    connectors_path = Path(connectors_dir)

    if not connectors_path.exists():
        print(f"⚠️  Connectors directory not found: {connectors_dir}")
        return connectors

    for folder in sorted(connectors_path.iterdir()):
        # Skip non-directories, template, and hidden folders
        if not folder.is_dir():
            continue
        if folder.name.startswith("_") or folder.name.startswith("."):
            continue

        connector_file = folder / "connector.py"
        if not connector_file.exists():
            print(f"⚠️  Skipping {folder.name}/ — no connector.py found")
            continue

        try:
            # Dynamically import the connector module
            spec = importlib.util.spec_from_file_location(
                f"connectors.{folder.name}.connector",
                str(connector_file)
            )
            module = importlib.util.module_from_spec(spec)

            # Add the connector's directory to sys.path temporarily
            # so it can import its own modules
            old_path = sys.path.copy()
            sys.path.insert(0, str(folder))
            spec.loader.exec_module(module)
            sys.path = old_path

            # Validate the contract
            if not hasattr(module, "TOOLS"):
                print(f"⚠️  Skipping {folder.name}/ — connector.py missing TOOLS list")
                continue
            if not hasattr(module, "handle"):
                print(f"⚠️  Skipping {folder.name}/ — connector.py missing handle() function")
                continue
            if not isinstance(module.TOOLS, list):
                print(f"⚠️  Skipping {folder.name}/ — TOOLS is not a list")
                continue
            if not callable(module.handle):
                print(f"⚠️  Skipping {folder.name}/ — handle is not callable")
                continue

            # Check is_connected() if defined; assume connected if missing
            if hasattr(module, "is_connected") and callable(module.is_connected):
                if not module.is_connected():
                    print(f"⏭️  Skipping {folder.name}/ — not connected")
                    continue

            connectors[folder.name] = {
                "tools": module.TOOLS,
                "handle": module.handle,
                "path": str(folder),
            }
            print(f"✅ Loaded connector: {folder.name} ({len(module.TOOLS)} tools)")

        except Exception as e:
            print(f"⚠️  Error loading {folder.name}/: {e}")
            continue

    return connectors


def get_all_tools(connectors: dict) -> list:
    """Flatten all tools from all connectors into one list."""
    all_tools = []
    for name, connector in connectors.items():
        all_tools.extend(connector["tools"])
    return all_tools


if __name__ == "__main__":
    # Quick test — run this to see what connectors are discovered
    connectors = load_connectors()
    print(f"\n📦 Loaded {len(connectors)} connector(s)")
    for name, c in connectors.items():
        print(f"  {name}: {[t['name'] for t in c['tools']]}")
