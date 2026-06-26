# drift-watch

> Structural drift detector for AI vendor API responses

---

## The Problem

When an AI vendor ships a silent API update, a field can move three levels deeper in the JSON response, and nothing throws an error — your parser just reads `null` where it used to read `0.002`, and every cost dashboard goes to zero. The incident rarely surfaces through alerts; it surfaces when a customer notices their spend tracker shows $0 for three days and calls to ask what happened. `drift-watch` catches that the day it happens by comparing the *shape* of a response — its field paths and types — not just whether the request succeeded.

---

## What it detects

| Signal | Severity | Description |
|--------|----------|-------------|
| Fields removed from a response | 🚨 **Critical** | A field your parser relies on has disappeared |
| Fields that changed type (e.g. `float → string`) | 🚨 **Critical** | Silent misparse — `"0.004"` reads as truthy, not as a number |
| New fields that appeared | ℹ️ **Informational** | Vendor added data; existing parsers still work fine |

---

## How to run

```bash
pip install -r requirements.txt
python main.py
```

The tool exits with code **0** if all schemas are stable, and **code 1** if any critical drift is found — making it a drop-in CI/CD gate.

---

## Run tests

```bash
pytest tests/ -v
```

---

## Vendors covered

| Vendor | Drift Scenario Simulated |
|--------|--------------------------|
| OpenAI | `usage.cost` moved to `billing.cost` — silently unreachable |
| Claude | `usage.cost_usd` silently removed entirely |
| Cursor | `cost` type changed `float → string`; `tokens_used` renamed `token_count` |

---

## Project Structure

```
drift-watch/
├── core/
│   └── differ.py          # get_shape() and compare_shapes()
├── fixtures/
│   ├── openai_before.json
│   ├── openai_after.json
│   ├── claude_before.json
│   ├── claude_after.json
│   ├── cursor_before.json
│   └── cursor_after.json
├── tests/
│   └── test_differ.py     # 6 pytest tests
├── main.py                # Rich CLI entrypoint
├── requirements.txt
└── README.md
```

---

## How it works

`get_shape()` recursively walks any JSON object and returns a **flat dictionary** mapping every field path to its Python type name:

```python
get_shape({"usage": {"cost": 0.002}})
# → {"usage": "dict", "usage.cost": "float"}
```

`compare_shapes(before, after)` diffs two shapes and classifies every difference:

```python
result = compare_shapes(before, after)
# {
#   "removed":      [{"field": "usage.cost", "was_type": "float"}],
#   "added":        [{"field": "billing.cost", "new_type": "float"}],
#   "type_changed": [],
#   "has_drift":    True
# }
```

`has_drift` is `True` only when something was **removed** or **type-changed** — not merely added.

---

## What's missing (honest gaps)

- **No real-time polling** — currently runs manually or in CI; no daemon mode
- **Array schemas only inspect the first item** — heterogeneous arrays are not fully modelled
- **No webhook / Slack alert integration yet** — output is terminal-only
- **No real captured payloads** — fixtures are carefully crafted drift simulations, not live traffic captures

---

## Why this matters for Oximy

Oximy's core value proposition is giving enterprises accurate, real-time visibility into their AI spend — and that visibility collapses the moment a vendor silently renames or removes a cost field without a version bump. `drift-watch` acts as the early-warning layer between vendor API changes and Oximy's parsers, catching schema shifts before they propagate into silent zero-cost readings that erode customer trust.
