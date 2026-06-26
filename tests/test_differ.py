"""
tests/test_differ.py
---------------------
Pytest suite for core/differ.py — 6 tests covering every drift scenario.

Run with:
    pytest tests/ -v
"""

import json
import pathlib
import sys

import pytest

# Allow imports from the project root regardless of working directory
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from core.differ import compare_shapes, get_shape

# Path to fixture files
FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "fixtures"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _load(filename: str) -> dict:
    return json.loads((FIXTURES / filename).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Test 1 — removed field is detected as critical drift
# ---------------------------------------------------------------------------

def test_detects_removed_field():
    """usage.cost present in before, missing in after → has_drift True."""
    before = {
        "usage": {
            "prompt_tokens": 100,
            "cost": 0.002,
        }
    }
    after = {
        "usage": {
            "prompt_tokens": 100,
        }
    }

    result = compare_shapes(before, after)

    assert result["has_drift"] is True, "Expected has_drift=True when a field is removed"

    removed_fields = [item["field"] for item in result["removed"]]
    assert "usage.cost" in removed_fields, (
        f"Expected 'usage.cost' in removed fields, got: {removed_fields}"
    )


# ---------------------------------------------------------------------------
# Test 2 — type change (float → string) is detected as critical drift
# ---------------------------------------------------------------------------

def test_detects_type_change():
    """cost goes from float to str → has_drift True, type_changed populated."""
    before = {"cost": 0.004}
    after = {"cost": "0.004"}

    result = compare_shapes(before, after)

    assert result["has_drift"] is True, "Expected has_drift=True on type change"

    type_changed_fields = [item["field"] for item in result["type_changed"]]
    assert "cost" in type_changed_fields, (
        f"Expected 'cost' in type_changed, got: {type_changed_fields}"
    )

    # Confirm the was/now values are recorded correctly
    cost_change = next(i for i in result["type_changed"] if i["field"] == "cost")
    assert cost_change["was"] == "float"
    assert cost_change["now"] == "str"


# ---------------------------------------------------------------------------
# Test 3 — identical payloads produce no drift
# ---------------------------------------------------------------------------

def test_no_drift_on_identical():
    """Same payload twice → has_drift False, all lists empty."""
    payload = {
        "id": "chatcmpl-123",
        "model": "gpt-4",
        "usage": {"prompt_tokens": 100, "cost": 0.002},
    }

    result = compare_shapes(payload, payload)

    assert result["has_drift"] is False, "Identical payloads must not flag drift"
    assert result["removed"] == []
    assert result["type_changed"] == []
    assert result["added"] == []


# ---------------------------------------------------------------------------
# Test 4 — added-only fields are informational, NOT critical drift
# ---------------------------------------------------------------------------

def test_new_field_not_critical():
    """after gains a brand-new field → has_drift False, added has 1 item."""
    before = {"id": "abc", "model": "gpt-4"}
    after = {"id": "abc", "model": "gpt-4", "new_field": "surprise"}

    result = compare_shapes(before, after)

    assert result["has_drift"] is False, (
        "Adding a new field should NOT be flagged as critical drift"
    )
    assert len(result["added"]) == 1, f"Expected 1 added field, got: {result['added']}"
    assert result["added"][0]["field"] == "new_field"


# ---------------------------------------------------------------------------
# Test 5 — removal 3 levels deep is correctly detected
# ---------------------------------------------------------------------------

def test_deeply_nested_removal():
    """Field 3 levels deep removed → detected in removed list with correct path."""
    before = {
        "level1": {
            "level2": {
                "level3": {
                    "secret_cost": 9.99
                }
            }
        }
    }
    after = {
        "level1": {
            "level2": {
                "level3": {}
            }
        }
    }

    result = compare_shapes(before, after)

    assert result["has_drift"] is True, "Deep nested removal should flag drift"

    removed_fields = [item["field"] for item in result["removed"]]
    assert "level1.level2.level3.secret_cost" in removed_fields, (
        f"Expected deeply nested field in removed, got: {removed_fields}"
    )


# ---------------------------------------------------------------------------
# Test 6 — all 3 vendor fixture pairs show has_drift True
# ---------------------------------------------------------------------------

def test_all_three_vendors():
    """Load real fixture files and assert all three vendors show critical drift."""
    vendors = [
        ("openai_before.json", "openai_after.json", "OpenAI"),
        ("claude_before.json", "claude_after.json", "Claude"),
        ("cursor_before.json", "cursor_after.json", "Cursor"),
    ]

    for before_file, after_file, vendor_name in vendors:
        before = _load(before_file)
        after = _load(after_file)

        result = compare_shapes(before, after)

        assert result["has_drift"] is True, (
            f"{vendor_name}: expected has_drift=True but got False.\n"
            f"  removed={result['removed']}\n"
            f"  type_changed={result['type_changed']}"
        )
