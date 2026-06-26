"""
core/differ.py
--------------
Structural drift detection for AI vendor API responses.

Provides two public functions:
  - get_shape(obj, path="")   : Flatten any JSON object to a path→type dict.
  - compare_shapes(before, after) : Diff two JSON objects, classify changes.
"""

from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _type_name(value: Any) -> str:
    """Return a human-readable type label for a JSON value."""
    if value is None:
        return "NoneType"
    return type(value).__name__  # int, float, str, bool, dict, list


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
        A dictionary with four keys:

        - ``"removed"``      : list of ``{"field": str, "was_type": str}``
          Fields present in *before* that are missing in *after*.
        - ``"added"``        : list of ``{"field": str, "new_type": str}``
          Fields present in *after* that did not exist in *before*.
        - ``"type_changed"`` : list of ``{"field": str, "was": str, "now": str}``
          Fields present in both but whose type changed.
        - ``"has_drift"``    : bool
          ``True`` if any field was removed OR changed type.
          Added-only responses are considered *growth*, not drift.

    Notes:
        Array schemas are inferred from the first element only.
        Empty arrays in *after* will surface nested fields as removed.
    """
    shape_before = get_shape(before)
    shape_after = get_shape(after)

    removed: list[dict] = []
    added: list[dict] = []
    type_changed: list[dict] = []

    # Fields in before — check for removal or type change
    for field, was_type in shape_before.items():
        if field not in shape_after:
            removed.append({"field": field, "was_type": was_type})
        elif shape_after[field] != was_type:
            type_changed.append(
                {"field": field, "was": was_type, "now": shape_after[field]}
            )

    # Fields in after that didn't exist before
    for field, new_type in shape_after.items():
        if field not in shape_before:
            added.append({"field": field, "new_type": new_type})

    has_drift = bool(removed or type_changed)

    return {
        "removed": removed,
        "added": added,
        "type_changed": type_changed,
        "has_drift": has_drift,
    }
