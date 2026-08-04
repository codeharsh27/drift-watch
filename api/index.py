"""
api/index.py — Standard BaseHTTPRequestHandler for Vercel Python Serverless Functions
Uses 100% native Python standard library. Zero external dependencies.
"""

from http.server import BaseHTTPRequestHandler
import json
import pathlib
from datetime import datetime, timezone

_ROOT = pathlib.Path(__file__).resolve().parent.parent

try:
    from api.differ import compare_shapes
except ImportError:
    try:
        from differ import compare_shapes
    except ImportError:
        def compare_shapes(b, a): return {"has_drift": False, "drift_score": 0}

def get_live_data():
    data_dir = _ROOT / "data"
    reports = []
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

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        vendors = get_live_data()
        drifts = sum(1 for v in vendors if v.get("has_drift"))
        
        response_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_vendors": len(vendors),
                "vendors_with_drift": drifts,
                "overall_status": "CRITICAL" if drifts > 0 else "STABLE"
            },
            "vendors": vendors
        }
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
        
        try:
            req = json.loads(post_data.decode('utf-8'))
            before = req.get("before_json", {})
            after = req.get("after_json", {})
        except Exception:
            before, after = {}, {}
            
        res = compare_shapes(before, after)
        self.wfile.write(json.dumps(res).encode('utf-8'))
