"""
core/differ.py
--------------
Structural drift detection for AI vendor API responses.

Provides two public functions:
  - get_shape(obj, path="")        : Flatten any JSON object to a path→type dict.
  - compare_shapes(before, after)  : Diff two JSON objects, classify changes.

v2 additions (backward-compatible):
  - Value snapshots (before_value, after_value) in all change records
  - Severity labels ("critical" / "info") on every change record
  - drift_score (0–100) on the compare result
  - detected_at ISO timestamp on the compare result
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _type_name(value: Any) -> str:
    """Return a human-readable type label for a JSON value."""
    if value is None:
        return "NoneType"
    return type(value).__name__  # int, float, str, bool, dict, list


def _safe_preview(value: Any, max_len: int = 40) -> str:
    """Return a short string preview of any value, truncated if needed."""
    if value is None:
        return "null"
    preview = str(value)
    if len(preview) > max_len:
        return preview[:max_len] + "…"
    return preview


def _get_values(obj: Any, path: str = "") -> dict[str, Any]:
    """Mirror of get_shape but records the actual Python values at each path.

    Used internally by compare_shapes to populate before_value/after_value
    fields in the diff result. Both dict/list nodes AND primitives are stored
    so that removals of entire nested objects can still show a preview.
    """
    values: dict[str, Any] = {}

    if isinstance(obj, dict):
        if path:
            values[path] = obj          # store the dict node itself too
        for key, value in obj.items():
            child_path = f"{path}.{key}" if path else key
            values.update(_get_values(value, child_path))

    elif isinstance(obj, list):
        if path:
            values[path] = obj          # store the list node itself
        if obj:
            item_path = f"{path}[0]" if path else "[0]"
            values.update(_get_values(obj[0], item_path))

    else:
        # Primitive: str, int, float, bool, NoneType
        if path:
            values[path] = obj

    return values


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_shape(obj: Any, path: str = "") -> dict[str, str]:
    """Recursively walk a JSON object and return a flat path → type mapping.

    Args:
        obj:  Any JSON-decoded Python object (dict, list, or primitive).
        path: Dot-separated path prefix accumulated during recursion.

    Returns:
        A flat dictionary where every key is a dot-separated field path and
        every value is the Python type name of that field, e.g.::

            {"usage": "dict", "usage.cost": "float", "choices": "list",
             "choices[0]": "dict", "choices[0].message": "dict",
             "choices[0].message.role": "str"}

    Examples:
        >>> get_shape({"usage": {"cost": 0.002}})
        {'usage': 'dict', 'usage.cost': 'float'}

    Notes:
        - Arrays: only the first element is inspected to infer element schema.
        - Empty arrays produce no child entries.
    """
    shape: dict[str, str] = {}

    if isinstance(obj, dict):
        if path:
            shape[path] = "dict"
        for key, value in obj.items():
            child_path = f"{path}.{key}" if path else key
            shape.update(get_shape(value, child_path))

    elif isinstance(obj, list):
        if path:
            shape[path] = "list"
        # Only inspect the first item to infer list element schema.
        if obj:
            item_path = f"{path}[0]" if path else "[0]"
            shape.update(get_shape(obj[0], item_path))

    else:
        # Primitive: str, int, float, bool, NoneType
        if path:
            shape[path] = _type_name(obj)

    return shape


def compare_shapes(before: Any, after: Any) -> dict:
    """Compare two JSON objects and classify structural differences.

    Args:
        before: The baseline JSON object (previously captured response).
        after:  The current JSON object (latest vendor response).

    Returns:
        A dictionary with the following keys:

        - ``"removed"``      : list of records for fields gone from *after*
          Each record: ``{field, was_type, before_value, after_value, severity}``
        - ``"added"``        : list of records for fields new in *after*
          Each record: ``{field, new_type, after_value, severity}``
        - ``"type_changed"`` : list of records where the type flipped
          Each record: ``{field, was, now, before_value, after_value, severity}``
        - ``"has_drift"``    : bool — True if any removal or type change occurred
        - ``"drift_score"``  : int 0-100 — % of baseline fields that are critical
        - ``"detected_at"``  : ISO-8601 UTC timestamp string

    Notes:
        Added-only changes set ``has_drift=False`` — they are growth, not drift.
        Array schemas are inferred from the first element only.
    """
    shape_before = get_shape(before)
    shape_after  = get_shape(after)
    vals_before  = _get_values(before)
    vals_after   = _get_values(after)

    removed:      list[dict] = []
    added:        list[dict] = []
    type_changed: list[dict] = []

    # Fields in before — check for removal or type change
    for field, was_type in shape_before.items():
        if field not in shape_after:
            removed.append({
                "field":        field,
                "was_type":     was_type,
                "before_value": _safe_preview(vals_before.get(field)),
                "after_value":  "null",
                "severity":     "critical",
            })
        elif shape_after[field] != was_type:
            type_changed.append({
                "field":        field,
                "was":          was_type,
                "now":          shape_after[field],
                "before_value": _safe_preview(vals_before.get(field)),
                "after_value":  _safe_preview(vals_after.get(field)),
                "severity":     "critical",
            })

    # Fields in after that didn't exist before
    for field, new_type in shape_after.items():
        if field not in shape_before:
            added.append({
                "field":       field,
                "new_type":    new_type,
                "after_value": _safe_preview(vals_after.get(field)),
                "severity":    "info",
            })

    has_drift = bool(removed or type_changed)

    # drift_score: what % of baseline fields are critically broken
    total_fields  = len(shape_before) or 1
    critical_hits = len(removed) + len(type_changed)
    drift_score   = min(100, round(critical_hits / total_fields * 100))

    return {
        "removed":      removed,
        "added":        added,
        "type_changed": type_changed,
        "has_drift":    has_drift,
        "drift_score":  drift_score,
        "detected_at":  datetime.now(timezone.utc).isoformat(),
    }
