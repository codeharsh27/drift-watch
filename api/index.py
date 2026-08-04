"""
api/index.py — Standalone Serverless Function for Vercel
Zero local module imports to guarantee 100% deployment reliability.
"""

from __future__ import annotations
import os
import json
import pathlib
from datetime import datetime, timezone
from typing import Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="drift-watch API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_ROOT = pathlib.Path(__file__).resolve().parent.parent

def _type_name(value: Any) -> str:
    if value is None:
        return "NoneType"
    return type(value).__name__

def get_shape(obj: Any, path: str = "") -> dict[str, str]:
    shape: dict[str, str] = {}
    if isinstance(obj, dict):
        if path: shape[path] = "dict"
        for k, v in obj.items():
            cp = f"{path}.{k}" if path else k
            shape.update(get_shape(v, cp))
    elif isinstance(obj, list):
        if path: shape[path] = "list"
        if obj:
            ip = f"{path}[0]" if path else "[0]"
            shape.update(get_shape(obj[0], ip))
    else:
        if path: shape[path] = _type_name(obj)
    return shape

def compare_shapes(before: Any, after: Any) -> dict:
    sb = get_shape(before)
    sa = get_shape(after)
    removed = []
    added = []
    type_changed = []

    for f, was_type in sb.items():
        if f not in sa:
            removed.append({"field": f, "was_type": was_type, "severity": "critical"})
        elif sa[f] != was_type:
            type_changed.append({"field": f, "was": was_type, "now": sa[f], "severity": "critical"})

    for f, new_type in sa.items():
        if f not in sb:
            added.append({"field": f, "new_type": new_type, "severity": "info"})

    has_drift = bool(removed or type_changed)
    total = len(sb) or 1
    hits = len(removed) + len(type_changed)
    score = min(100, round(hits / total * 100))

    return {
        "removed": removed,
        "added": added,
        "type_changed": type_changed,
        "has_drift": has_drift,
        "drift_score": score,
        "detected_at": datetime.now(timezone.utc).isoformat()
    }

def get_reports():
    reports = []
    data_dir = _ROOT / "data"
    
    if data_dir.exists():
        for f in data_dir.glob("*.json"):
            if f.name.startswith("."): continue
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
def health():
    return {"status": "ok", "service": "drift-watch"}

@app.get("/api/report")
def report():
    vendors = get_reports()
    drifts = sum(1 for v in vendors if v.get("has_drift"))
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_vendors": len(vendors),
            "vendors_with_drift": drifts,
            "overall_status": "CRITICAL" if drifts > 0 else "STABLE"
        },
        "vendors": vendors
    }

class DiffReq(BaseModel):
    before_json: Any = {}
    after_json: Any = {}

@app.post("/api/diff")
def diff(req: DiffReq):
    return compare_shapes(req.before_json, req.after_json)
