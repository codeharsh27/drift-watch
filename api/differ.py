"""
api/differ.py — In-memory shape hashing engine
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

def _type_name(value: Any) -> str:
    if value is None: return "NoneType"
    return type(value).__name__

def get_shape(obj: Any, path: str = "") -> dict[str, str]:
    shape: dict[str, str] = {}
    if isinstance(obj, dict):
        if path: shape[path] = "dict"
        for key, value in obj.items():
            cp = f"{path}.{key}" if path else key
            shape.update(get_shape(value, cp))
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
