"""
run_all.py — Discover and validate all connectors in the repo.

Usage:
    python tests/run_all.py
"""

import sys
import subprocess
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent
CONNECTORS_DIR = PROJECT_ROOT / "connectors"
VALIDATE_SCRIPT = PROJECT_ROOT / "tests" / "validate_connector.py"


def main():
    print("\n🦀 ClawFounder — Running All Connector Validations")
    print("=" * 55)

    connectors = sorted([
        d for d in CONNECTORS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_") and not d.name.startswith(".")
    ])

    if not connectors:
        print("\n⚠️  No connectors found in connectors/")
        sys.exit(1)

    results = {}
    total_passed = 0
    total_failed = 0

    # ── Step 1: Structure Validation ──────────────────────────────
    print(f"\n📋 Step 1: Structure Validation ({len(connectors)} connectors)")
    print("─" * 55)

    for connector_dir in connectors:
        name = connector_dir.name
        result = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), str(connector_dir)],
            capture_output=True,
            text=True,
        )
        passed = result.returncode == 0
        results[name] = {"structure": passed}

        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed and result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line.strip().startswith("❌") or line.strip().startswith("⚠️"):
                    print(f"     {line.strip()}")

    # ── Step 2: Unit Tests ────────────────────────────────────────
    print(f"\n🧪 Step 2: Unit Tests")
    print("─" * 55)

    for connector_dir in connectors:
        name = connector_dir.name
        test_file = connector_dir / "test_connector.py"

        if not test_file.exists():
            print(f"  ⚠️  {name} — no test_connector.py")
            results[name]["tests"] = False
            continue

        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=str(connector_dir),
        )
        passed = result.returncode == 0
        results[name]["tests"] = passed

        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            # Show failure summary
            for line in result.stdout.strip().split("\n"):
                if "FAILED" in line or "ERROR" in line:
                    print(f"     {line.strip()}")

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'=' * 55}")
    print("📊 Summary")
    print(f"{'─' * 55}")

    for name, result in results.items():
        struct = "✅" if result.get("structure") else "❌"
        tests = "✅" if result.get("tests") else "❌"
        all_passed = result.get("structure") and result.get("tests")
        if all_passed:
            total_passed += 1
        else:
            total_failed += 1
        print(f"  {name:20s} Structure: {struct}  Tests: {tests}")

    print(f"\n  Total: {total_passed} passed, {total_failed} failed, {len(connectors)} total")
    print()

    sys.exit(0 if total_failed == 0 else 1)


if __name__ == "__main__":
    main()
