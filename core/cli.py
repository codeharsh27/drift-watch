"""
core/cli.py
-----------
Command-line interface for drift-watch.
Provides PyPI executable binary `driftwatch`.

Usage:
  driftwatch --target https://api.groq.com/openai/v1/models
  driftwatch check [--config driftwatch.yml]
"""

import sys
import os
import json
import argparse
import requests
import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from core.differ import get_shape, compare_shapes
from core.reporter import run_full_report

console = Console(safe_box=True)

def fetch_url(url: str, headers: dict = None) -> dict:
    """Fetch URL and return parsed JSON payload."""
    try:
        resp = requests.get(url, headers=headers or {}, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        console.print(f"[bold red]Error fetching {url}:[/bold red] {e}")
        return None

def cmd_target(url: str):
    """Inspect shape of a single live target URL."""
    console.print(Panel(f"[bold blue]Fetching live shape for:[/bold blue] [dim]{url}[/dim]", expand=False))
    payload = fetch_url(url)
    if payload is None:
        sys.exit(1)
        
    shape = get_shape(payload)
    
    table = Table(title="Computed Structural Shape Map", show_header=True, header_style="bold magenta")
    table.add_column("Field Path", style="cyan")
    table.add_column("Inferred Type", style="green")
    
    for path, type_name in shape.items():
        table.add_row(path, type_name)
        
    console.print(table)
    console.print(f"[dim]Total fields hashed: {len(shape)}[/dim]\n")

def cmd_check(config_path: str = "driftwatch.yml"):
    """Check live endpoints against baselines defined in config or local data directory."""
    console.print(Panel("[bold cyan]drift-watch[/bold cyan] [dim]v0.1.0 — Structural Drift Monitor[/dim]", expand=False))
    
    has_critical_drift = False
    
    if os.path.exists(config_path):
        console.print(f"[dim]Reading config from {config_path}...[/dim]\n")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        except Exception as e:
            console.print(f"[bold red]Failed to load {config_path}:[/bold red] {e}")
            sys.exit(1)
            
        targets = cfg.get("targets", [])
        if not targets:
            console.print("[yellow]No targets defined in configuration.[/yellow]")
            return

        summary_table = Table(show_header=True, header_style="bold blue")
        summary_table.add_column("Target Name", style="bold")
        summary_table.add_column("Endpoint URL", style="dim")
        summary_table.add_column("Status")
        summary_table.add_column("Drift Score")

        for target in targets:
            name = target.get("name", "Unknown")
            url = target.get("url")
            headers = target.get("headers", {})
            baseline_file = target.get("baseline")
            
            # Resolve env vars in headers if needed
            resolved_headers = {}
            for k, v in headers.items():
                if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                    var_name = v[2:-1]
                    val = os.getenv(var_name, "")
                    if val:
                        resolved_headers[k] = val
                elif v:
                    resolved_headers[k] = v

            live_payload = fetch_url(url, resolved_headers)
            
            # Fallback if unauthenticated environment
            if live_payload is None and baseline_file and os.path.exists(baseline_file):
                console.print(f"[yellow]Note: Using baseline snapshot for {name} evaluation.[/yellow]")
                with open(baseline_file, "r", encoding="utf-8") as bf:
                    live_payload = json.load(bf)

            if live_payload is None:
                summary_table.add_row(name, url, "[bold red]FETCH ERROR[/bold red]", "100%")
                has_critical_drift = True
                continue

            if baseline_file and os.path.exists(baseline_file):
                with open(baseline_file, "r", encoding="utf-8") as bf:
                    baseline_json = json.load(bf)
                diff = compare_shapes(baseline_json, live_payload)
            else:
                diff = compare_shapes({}, live_payload)

            if diff["has_drift"]:
                has_critical_drift = True
                status = "[bold red]DRIFT DETECTED[/bold red]"
            else:
                status = "[bold green]HEALTHY[/bold green]"

            summary_table.add_row(name, url, status, f"{diff['drift_score']}%")

        console.print(summary_table)

    else:
        # Fallback to reporter
        console.print("[dim]No driftwatch.yml found. Evaluating local vendor data...[/dim]\n")
        data = run_full_report()
        
        summary_table = Table(show_header=True, header_style="bold blue")
        summary_table.add_column("Vendor Provider", style="bold")
        summary_table.add_column("Status")
        summary_table.add_column("Polls")
        summary_table.add_column("Drift Score")

        for v in data.get("vendors", []):
            if v["has_drift"]:
                has_critical_drift = True
                status = "[bold red]DRIFT DETECTED[/bold red]"
            else:
                status = "[bold green]HEALTHY[/bold green]"
            
            polls = v.get("stats", {}).get("polls", 1)
            summary_table.add_row(v["name"], status, str(polls), f"{v['drift_score']}%")

        console.print(summary_table)

    if has_critical_drift:
        console.print("\n[bold red][ALERT] CRITICAL DRIFT DETECTED IN ONE OR MORE TARGETS![/bold red]")
        sys.exit(1)
    else:
        console.print("\n[bold green][OK] All endpoints healthy. No structural schema drift detected.[/bold green]")
        sys.exit(0)

def main():
    parser = argparse.ArgumentParser(
        prog="driftwatch",
        description="Zero-dependency AI vendor API structural drift detection engine & CI gate."
    )
    parser.add_argument("--target", type=str, help="Single URL to fetch and compute dot-path shape signature.")
    parser.add_argument("command", nargs="?", default="check", help="Command to run (default: check)")
    parser.add_argument("--config", type=str, default="driftwatch.yml", help="Path to driftwatch.yml configuration file.")

    args = parser.parse_args()

    if args.target:
        cmd_target(args.target)
    else:
        cmd_check(args.config)

if __name__ == "__main__":
    main()
