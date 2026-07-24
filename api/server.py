"""
api/server.py
-------------
FastAPI REST server for drift-watch.

Serves both the JSON API and the frontend static files from a single process.

Endpoints:
  GET /                    → frontend dashboard (index.html)
  GET /api/health          → health check
  GET /api/report          → full drift report for all vendors
  GET /api/vendor/{name}   → single-vendor drift report

Run:
    python -m api.server
    # then open: http://localhost:8000
"""

from __future__ import annotations

import pathlib
import sys

# Ensure project root is importable regardless of cwd
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any

from core.reporter import VENDORS, run_full_report, run_vendor_report
from core.differ import compare_shapes

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="drift-watch API",
    version="2.0.0",
    description="Structural drift detector for AI vendor API responses.",
)

FRONTEND_DIR = _ROOT / "frontend"

# CORS — allow all origins for local development / CI usage
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Serve CSS, JS, images etc. from /static/*
app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static",
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def serve_frontend() -> FileResponse:
    """Serve the SPA dashboard."""
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    """Simple liveness probe."""
    return {"status": "ok", "service": "drift-watch", "version": "2.0.0"}


@app.get("/api/report", tags=["drift"])
async def get_report() -> dict:
    """Return a full drift report for every registered vendor.

    The response contains a top-level ``summary`` and a ``vendors`` list,
    each entry carrying ``removed``, ``added``, ``type_changed``,
    ``has_drift``, and ``drift_score`` (0-100).
    """
    return run_full_report()


@app.get("/api/vendor/{name}", tags=["drift"])
async def get_vendor(name: str) -> dict:
    """Return a drift report for a single vendor by name (case-insensitive).

    Example: GET /api/vendor/openai
    """
    vendor = next(
        (v for v in VENDORS if v["name"].lower() == name.lower()),
        None,
    )
    if vendor is None:
        known = [v["name"] for v in VENDORS]
        raise HTTPException(
            status_code=404,
            detail=f"Vendor '{name}' not found. Known vendors: {known}",
        )
    return run_vendor_report(vendor)


class DiffRequest(BaseModel):
    before_json: Any
    after_json: Any

@app.post("/api/diff", tags=["drift"])
async def run_live_diff(req: DiffRequest) -> dict:
    """Run a live drift detection against two arbitrary JSON payloads."""
    return compare_shapes(req.before_json, req.after_json)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    print("\n  drift-watch API server starting...")
    print("  Dashboard -> http://localhost:8000")
    print("  API docs  -> http://localhost:8000/docs\n")
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
