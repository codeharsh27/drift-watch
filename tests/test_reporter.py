"""
tests/test_reporter.py
-----------------------
Tests for core/reporter.py — covering report structure, vendor drift,
drift_score bounds, and value snapshot presence.

Run with:
    pytest tests/ -v
"""

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from core.reporter import VENDORS, run_full_report, run_vendor_report


# ---------------------------------------------------------------------------
# Test 7 — full report has the required top-level structure
# ---------------------------------------------------------------------------

def test_run_full_report_structure():
    """Full report must have generated_at, summary, and vendors keys."""
    report = run_full_report()

    assert "generated_at" in report, "Missing 'generated_at'"
    assert "summary"      in report, "Missing 'summary'"
    assert "vendors"      in report, "Missing 'vendors'"

    assert report["summary"]["total_vendors"] == len(VENDORS)
    assert len(report["vendors"]) == len(VENDORS)


# ---------------------------------------------------------------------------
# Test 8 — all 3 fixture vendor pairs show critical drift in full report
# ---------------------------------------------------------------------------

def test_full_report_all_vendors_drifted():
    """All 3 fixture vendor pairs must flag critical drift."""
    report = run_full_report()

    assert report["summary"]["overall_status"] == "CRITICAL", (
        f"Expected CRITICAL, got {report['summary']['overall_status']}"
    )
    for vendor in report["vendors"]:
        assert vendor["has_drift"] is True, (
            f"{vendor['name']}: expected has_drift=True"
        )


# ---------------------------------------------------------------------------
# Test 9 — drift_score is a valid 0-100 integer
# ---------------------------------------------------------------------------

def test_vendor_report_drift_score_bounds():
    """Every vendor report must include drift_score within [0, 100]."""
    report = run_full_report()
    for vendor in report["vendors"]:
        score = vendor.get("drift_score")
        assert score is not None, f"{vendor['name']}: missing drift_score"
        assert isinstance(score, int), f"{vendor['name']}: drift_score must be int"
        assert 0 <= score <= 100, (
            f"{vendor['name']}: drift_score {score} outside [0, 100]"
        )


# ---------------------------------------------------------------------------
# Test 10 — removed fields include before_value snapshot (v2 addition)
# ---------------------------------------------------------------------------

def test_removed_fields_have_value_snapshots():
    """Removed field records must carry before_value and after_value."""
    report = run_full_report()
    for vendor in report["vendors"]:
        for item in vendor["removed"]:
            assert "before_value" in item, (
                f"{vendor['name']}.{item['field']}: missing before_value"
            )
            assert "after_value" in item, (
                f"{vendor['name']}.{item['field']}: missing after_value"
            )
            # after_value for a removed field must indicate absence
            assert item["after_value"] == "null", (
                f"Expected after_value='null' for removed field, "
                f"got '{item['after_value']}'"
            )
