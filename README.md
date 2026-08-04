# 🛡️ drift-watch

> **Zero-dependency structural schema drift detection engine & CI gate for AI vendor APIs.**

[![PyPI](https://img.shields.io/badge/pip-install%20drift--watch-blue.svg)](https://pypi.org/project/drift-watch/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Live Dashboard](https://img.shields.io/badge/Live%20Dashboard-Operational-success)](https://drift-watch-one.vercel.app/)

Traditional HTTP monitoring catches `500 Internal Server Error` failures. **`drift-watch` catches `200 OK` responses that silently corrupt your application pipelines.**

AI vendors (Groq, Cohere, OpenAI, Gemini) update response schemas without major version bumps. If an endpoint silently drops `usage.cost` or converts a string ID to an integer, standard status checks pass—while downstream billing & analytics report `$0.00` spend. `drift-watch` recursively flattens live JSON payloads into dot-path signatures, diffing them against baselines to exit `1` on drift.

---

## ⚡ Terminal Demo

```text
$ driftwatch check --config driftwatch.yml

┌──────────────────────────────────────────────────────────┐
│ drift-watch v0.1.0 — Structural Drift Monitor            │
└──────────────────────────────────────────────────────────┘

Reading config from driftwatch.yml...

Target Name    Endpoint URL                            Status           Drift Score
─────────────────────────────────────────────────────────────────────────────────
Groq Models    https://api.groq.com/openai/v1/models   HEALTHY          0%
Cohere Models  https://api.cohere.com/v1/models        HEALTHY          0%
Gemini Models  https://generativelanguage.googleapis…  HEALTHY          0%

✓ All endpoints healthy. No structural schema drift detected.
```

---

## 🚀 Quickstart

Install via `pip`:

```bash
pip install drift-watch
```

### 1. Ad-Hoc Target Inspection
Flatten any live JSON API payload into a structural dot-path signature:

```bash
driftwatch --target https://api.groq.com/openai/v1/models
```

**Output:**
```text
Field Path              Inferred Type
──────────────────────────────────────
root                    dict
data                    list
data[0]                 dict
data[0].id              str
data[0].object          str
data[0].created         int
data[0].owned_by        str
```

### 2. CI/CD Schema Guard
Run batch schema drift checks defined in `driftwatch.yml`:

```bash
driftwatch check
```

---

## ⚙️ Configuration (`driftwatch.yml`)

Create a `driftwatch.yml` file in your project root:

```yaml
version: "1"

targets:
  - name: Groq Models
    url: https://api.groq.com/openai/v1/models
    method: GET
    baseline: .driftwatch/groq.json

  - name: Cohere Models
    url: https://api.cohere.com/v1/models
    method: GET
    headers:
      Authorization: Bearer ${COHERE_API_KEY}
    baseline: .driftwatch/cohere.json
```

---

## 🛡️ GitHub Actions CI Gating

Add `.github/workflows/drift.yml` to block deployment pipelines when critical schema drift occurs:

```yaml
name: Schema Drift Guard

on:
  schedule:
    - cron: '0 */6 * * *'
  workflow_dispatch:

jobs:
  drift-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with: { python-version: '3.10' }
      - run: pip install drift-watch
      - name: Run Schema Guard
        env:
          COHERE_API_KEY: ${{ secrets.COHERE_API_KEY }}
        run: driftwatch check --config driftwatch.yml
```

---

## 🌐 Live Platform Dashboard

We host a live monitoring feed polling active LLM providers (Cohere, Groq, Gemini) every 6 hours via GitHub Actions:

🔗 **Live Monitoring App:** [https://drift-watch-one.vercel.app/](https://drift-watch-one.vercel.app/)

---

## 📐 Architecture & Mechanism

```
[Live AI APIs] ──► [Live Poller] ──► [Shape Hashing Engine] ──► [Diff Evaluator] ──► [CI Gate & Alert]
```

1. **Shape Hashing**: Recursively flattens JSON objects to dot-path mappings (`{"usage": "dict", "usage.cost": "float"}`). Dynamic values are stripped.
2. **Set-Diffing**: Compares shapes against baselines to classify field removals (`was_type`), field additions (`new_type`), and mutated types (`was -> now`).
3. **Growth vs Drift**: Field additions set `has_drift=False` (API growth). Field removals and type mutations set `has_drift=True` (critical drift).
4. **CI Gating**: Exits with non-zero code `1` on critical drift, triggering Webhook alerts and gating deployment pipelines.

---

## 📄 License
MIT License. Created by [CodeHarsh](https://github.com/codeharsh27).
