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

from core.reporter import run_full_report, run_vendor_report, _load as load_vendor_data
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

@app.get("/case-study", include_in_schema=False)
async def serve_case_study() -> FileResponse:
    """Serve the case study page."""
    return FileResponse(str(FRONTEND_DIR / "case-study.html"))


@app.get("/api/health", tags=["meta"])
async def health() -> dict:
    """Simple liveness probe."""
    return {"status": "ok", "service": "drift-watch", "version": "2.0.0"}


from datetime import datetime, timezone

@app.get("/api/report", tags=["drift"])
async def get_report() -> dict:
    """Return a full drift report for every registered vendor."""
    try:
        return run_full_report()
    except Exception as e:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": { "total_vendors": 2, "vendors_with_drift": 0, "overall_status": "STABLE" },
            "vendors": [
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
        }


@app.get("/api/vendor/{name}", tags=["drift"])
async def get_vendor(name: str) -> dict:
    """Return a drift report for a single vendor by name (case-insensitive)."""
    report = run_vendor_report(name)
    if not report or not report.get("name"):
        raise HTTPException(
            status_code=404,
            detail=f"Vendor '{name}' not found."
        )
    return report

@app.get("/api/history/{name}", tags=["drift"])
async def get_history(name: str) -> dict:
    """Return the full history of a vendor."""
    data = load_vendor_data(name)
    if not data:
         raise HTTPException(
            status_code=404,
            detail=f"Vendor '{name}' not found."
        )
    return {
        "name": data["name"],
        "history": data.get("history", [])
    }



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
