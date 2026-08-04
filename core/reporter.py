"""
core/reporter.py
----------------
Generates structured JSON reports from live polled data.

Public API:
  - run_full_report()        → full report dict for all polled vendors
  - run_vendor_report(name)  → single-vendor report dict
"""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

ROOT     = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

def _load(vendor_name: str) -> dict:
    """Load and parse a JSON data file for a vendor."""
    file_path = DATA_DIR / f"{vendor_name.lower()}.json"
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))

def run_vendor_report(vendor_name: str) -> dict:
    """Return the latest drift report for a single vendor from live data."""
    data = _load(vendor_name)
    if not data:
        return {
            "name": vendor_name,
            "description": "No live data available yet.",
            "has_drift": False,
            "drift_score": 0,
            "removed": [],
            "added": [],
            "type_changed": [],
            "detected_at": datetime.now(timezone.utc).isoformat()
        }
        
    history = data.get("history", [])
    if not history:
        return {
            "name": data["name"],
            "description": data.get("description", ""),
            "has_drift": False,
            "drift_score": 0,
            "removed": [],
            "added": [],
            "type_changed": [],
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "polls": 0,
                "drifts_caught": 0,
                "since": datetime.now(timezone.utc).isoformat()
            }
        }
        
    latest = history[-1]
    drifts_caught = sum(1 for h in history if h.get("has_drift"))
    
    return {
        "name": data["name"],
        "description": data.get("description", ""),
        "has_drift": latest.get("has_drift", False),
        "drift_score": latest.get("drift_score", 0),
        "removed": latest.get("removed", []),
        "added": latest.get("added", []),
        "type_changed": latest.get("type_changed", []),
        "detected_at": latest.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "baseline": data.get("baseline", {}),
        "stats": {
            "polls": len(history),
            "drifts_caught": drifts_caught,
            "since": history[0].get("timestamp", datetime.now(timezone.utc).isoformat())
        }
    }

def run_full_report() -> dict:
    """Generate a complete drift report reading from all live data files."""
    vendor_reports = []
    
    if DATA_DIR.exists():
        for file_path in DATA_DIR.glob("*.json"):
            # Exclude anything that isn't a vendor file if needed
            vendor_name = file_path.stem
            report = run_vendor_report(vendor_name)
            if report.get("name"): # ensure valid
                vendor_reports.append(report)

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
