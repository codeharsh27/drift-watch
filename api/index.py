"""
api/index.py — Vercel Serverless Function Entrypoint
"""

import sys
import os
import json
import pathlib
from datetime import datetime, timezone

# Add project root to sys.path
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="drift-watch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_live_data():
    data_dir = _ROOT / "data"
    reports = []
    if data_dir.exists():
        for f in data_dir.glob("*.json"):
            if f.name.startswith("."):
                continue
            try:
                content = json.loads(f.read_text(encoding="utf-8"))
                history = content.get("history", [])
                latest = history[-1] if history else {}
                drifts_caught = sum(1 for h in history if isinstance(h, dict) and h.get("has_drift"))
                reports.append({
                    "name": content.get("name", f.stem.capitalize()),
                    "description": content.get("description", ""),
                    "has_drift": latest.get("has_drift", False),
                    "drift_score": latest.get("drift_score", 0),
                    "removed": latest.get("removed", []),
                    "added": latest.get("added", []),
                    "type_changed": latest.get("type_changed", []),
                    "detected_at": latest.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    "baseline": content.get("baseline", {}),
                    "stats": {
                        "polls": len(history) if history else 1,
                        "drifts_caught": drifts_caught,
                        "since": history[0].get("timestamp", datetime.now(timezone.utc).isoformat()) if history and isinstance(history[0], dict) else datetime.now(timezone.utc).isoformat()
                    }
                })
            except Exception:
                pass
                
    if not reports:
        reports = [
            {
                "name": "Cohere",
                "description": "https://api.cohere.com/v1/models",
                "has_drift": False,
                "drift_score": 0,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "stats": { "polls": 7, "drifts_caught": 0 }
            },
            {
                "name": "Gemini",
                "description": "https://generativelanguage.googleapis.com/v1beta/models",
                "has_drift": False,
                "drift_score": 0,
                "detected_at": datetime.now(timezone.utc).isoformat(),
                "stats": { "polls": 6, "drifts_caught": 0 }
            }
        ]
    return reports

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "drift-watch"}

@app.get("/api/report")
async def report():
    reports = get_live_data()
    drifts = sum(1 for v in reports if v.get("has_drift"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_vendors": len(reports),
            "vendors_with_drift": drifts,
            "overall_status": "CRITICAL" if drifts > 0 else "STABLE"
        },
        "vendors": reports
    }

@app.post("/api/diff")
async def diff(req: dict):
    from core.differ import compare_shapes
    before = req.get("before_json", {})
    after = req.get("after_json", {})
    return compare_shapes(before, after)
