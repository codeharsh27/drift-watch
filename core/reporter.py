"""
core/reporter.py
----------------
Generates structured JSON reports from all configured vendor fixture pairs.

Used by both:
  - main.py     (CLI rich output)
  - api/server.py  (REST API JSON responses)

Public API:
  - run_full_report()        → full report dict for all vendors
  - run_vendor_report(v)     → single-vendor report dict
  - VENDORS                  → list of vendor config dicts
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

from core.differ import compare_shapes

ROOT     = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

# ---------------------------------------------------------------------------
# Vendor registry — add new vendors here without touching anything else
# ---------------------------------------------------------------------------

VENDORS: list[dict] = [
    {
        "name":        "OpenAI",
        "description": "GPT-4 chat completion API",
        "before":      "openai_before.json",
        "after":       "openai_after.json",
    },
    {
        "name":        "Claude",
        "description": "Anthropic Messages API",
        "before":      "claude_before.json",
        "after":       "claude_after.json",
    },
    {
        "name":        "Cursor",
        "description": "Cursor code-assistant API",
        "before":      "cursor_before.json",
        "after":       "cursor_after.json",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load(filename: str) -> dict:
    """Load and parse a JSON fixture file."""
    return json.loads((FIXTURES / filename).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_vendor_report(vendor: dict) -> dict:
    """Run drift comparison for a single vendor and return a structured report.

    Args:
        vendor: A dict from the VENDORS list with keys:
                name, description, before, after.

    Returns:
        A dict merging vendor metadata with the compare_shapes result::

            {
              "name":         "OpenAI",
              "description":  "GPT-4 chat completion API",
              "has_drift":    True,
              "drift_score":  60,
              "removed":      [...],
              "added":        [...],
              "type_changed": [...],
              "detected_at":  "2026-07-24T17:10:00+00:00",
            }
    """
    before = _load(vendor["before"])
    after  = _load(vendor["after"])
    result = compare_shapes(before, after)
    return {
        "name":        vendor["name"],
        "description": vendor["description"],
        **result,
    }


def run_full_report() -> dict:
    """Generate a complete drift report for all registered vendors.

    Returns:
        A dict with three keys:

        - ``"generated_at"`` : ISO-8601 UTC timestamp for this run
        - ``"summary"``      : aggregate stats across all vendors
        - ``"vendors"``      : list of per-vendor report dicts

    Example::

        {
          "generated_at": "2026-07-24T17:10:00+00:00",
          "summary": {
            "total_vendors":     3,
            "vendors_with_drift": 3,
            "overall_status":    "CRITICAL"
          },
          "vendors": [...]
        }
    """
    vendor_reports = [run_vendor_report(v) for v in VENDORS]
    vendors_with_drift = sum(1 for v in vendor_reports if v["has_drift"])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_vendors":      len(vendor_reports),
            "vendors_with_drift": vendors_with_drift,
            "overall_status":     "CRITICAL" if vendors_with_drift > 0 else "STABLE",
        },
        "vendors": vendor_reports,
    }
