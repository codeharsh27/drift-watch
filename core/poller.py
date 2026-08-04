import os
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.differ import compare_shapes

DATA_DIR = _ROOT / "data"

TARGETS = [
    {
        "name": "Groq",
        "url": "https://api.groq.com/openai/v1/models",
        "env_key": "GROQ_API_KEY",
        "auth_type": "bearer"
    },
    {
        "name": "Cohere",
        "url": "https://api.cohere.com/v1/models",
        "env_key": "COHERE_API_KEY",
        "auth_type": "bearer"
    },
    {
        "name": "Gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/models",
        "env_key": "GEMINI_API_KEY",
        "auth_type": "query",
        "query_param": "key"
    },
    {
        "name": "OpenAI",
        "url": "https://api.openai.com/v1/models",
        "env_key": "OPENAI_API_KEY",
        "auth_type": "bearer"
    },
    {
        "name": "Anthropic",
        "url": "https://api.anthropic.com/v1/models",
        "env_key": "ANTHROPIC_API_KEY",
        "auth_type": "x-api-key",
        "header_key": "x-api-key"
    }
]

def post_webhook(webhook_url: str, vendor: str, removed: list, type_changed: list):
    """Post an alert to Slack/Discord."""
    if not webhook_url:
        return
        
    lines = [f"🚨 **Drift Detected for {vendor}!**"]
    
    for r in removed:
        lines.append(f" - **Removed:** `{r['field']}` (was {r['was_type']})")
        
    for tc in type_changed:
        lines.append(f" - **Type Changed:** `{tc['field']}` (was {tc['was']} -> now {tc['now']})")
        
    payload = {"content": "\n".join(lines)}
    
    req = urllib.request.Request(
        webhook_url, 
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    
    try:
        urllib.request.urlopen(req)
        print(f"[{vendor}] Webhook sent.")
    except Exception as e:
        print(f"[{vendor}] Failed to send webhook: {e}")

def run_poller():
    print("Starting drift-watch poller...")
    DATA_DIR.mkdir(exist_ok=True)
    
    webhook_url = os.environ.get("WEBHOOK_URL")

    for target in TARGETS:
        api_key = os.environ.get(target["env_key"])
        if not api_key:
            print(f"[{target['name']}] Skip: Missing {target['env_key']}")
            continue
            
        print(f"[{target['name']}] Polling {target['url']}...")
        
        # Build Request
        url = target["url"]
        headers = {}
        
        if target["auth_type"] == "bearer":
            headers["Authorization"] = f"Bearer {api_key}"
        elif target["auth_type"] == "x-api-key":
            headers[target.get("header_key", "x-api-key")] = api_key
            headers["anthropic-version"] = "2023-06-01"
        elif target["auth_type"] == "query":
            url += f"?{target['query_param']}={api_key}"
            
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req) as response:
                body = response.read().decode('utf-8')
                current_payload = json.loads(body)
        except urllib.error.HTTPError as e:
            try:
                # Even if it's an error, it's a JSON response we can diff!
                body = e.read().decode('utf-8')
                current_payload = json.loads(body)
            except:
                print(f"[{target['name']}] Failed to fetch and parse error JSON: {e}")
                continue
        except Exception as e:
            print(f"[{target['name']}] Request failed: {e}")
            continue

        file_path = DATA_DIR / f"{target['name'].lower()}.json"
        
        if not file_path.exists():
            # First run for this vendor: save baseline and skip diffing
            print(f"[{target['name']}] No baseline found. Saving as baseline.")
            data = {
                "name": target["name"],
                "description": f"Live polling from {target['url']}",
                "baseline": current_payload,
                "history": []
            }
            file_path.write_text(json.dumps(data, indent=2))
            continue
            
        # Read existing data
        data = json.loads(file_path.read_text())
        baseline_payload = data["baseline"]
        
        # Diff
        raw_diff = compare_shapes(baseline_payload, current_payload)
        
        # Noise Guard (Task 4): Ignore fields toggling between null and absent
        filtered_removed = [r for r in raw_diff["removed"] if r.get("was_type") != "NoneType"]
        filtered_added = [a for a in raw_diff["added"] if a.get("new_type") != "NoneType"]
        
        # We don't filter type_changed, because changing from/to NoneType is caught by added/removed in the shape hashing.
        # Wait, if a field changes from str to NoneType, the engine flags it as type_changed.
        # The user said: "ignore fields where a value is None/null on one side and the field is simply absent on the other"
        # That specifically means absent vs NoneType, which translates strictly to 'removed' with was_type=NoneType or 'added' with new_type=NoneType.
        
        has_drift = bool(filtered_removed or raw_diff["type_changed"])
        
        # Recompute score (approximate)
        total_fields = max(1, len(raw_diff["removed"]) + len(raw_diff["added"]) + len(raw_diff["type_changed"]) + 10) # rough, we just use the original score or 0 if no drift
        drift_score = raw_diff["drift_score"] if has_drift else 0
        
        diff_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "removed": filtered_removed,
            "added": filtered_added,
            "type_changed": raw_diff["type_changed"],
            "has_drift": has_drift,
            "drift_score": drift_score
        }
        
        data["history"].append(diff_record)
        
        # Limit history to 100 entries to prevent infinite file growth
        if len(data["history"]) > 100:
            data["history"] = data["history"][-100:]
            
        file_path.write_text(json.dumps(data, indent=2))
        
        print(f"[{target['name']}] Poll complete. Drift: {has_drift}")
        
        if has_drift:
            post_webhook(webhook_url, target["name"], filtered_removed, raw_diff["type_changed"])

if __name__ == "__main__":
    run_poller()
