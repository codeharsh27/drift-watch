"""
main.py
-------
drift-watch CLI entrypoint — v2.

Uses core.reporter for structured data and rich for colored output.
Exits with code 1 on any critical drift so CI/CD pipelines can gate on it.

Usage:
    python main.py
"""

from __future__ import annotations

import io
import sys

# Force UTF-8 output on Windows so unicode renders correctly
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.reporter import run_full_report

console = Console(force_terminal=True, highlight=False)


# ---------------------------------------------------------------------------
# Table renderers
# ---------------------------------------------------------------------------

def _removed_table(removed: list[dict]) -> Table:
    t = Table(
        title="[bold red]Removed Fields[/bold red]",
        box=box.ROUNDED,
        border_style="red",
        header_style="bold red",
        show_lines=True,
    )
    t.add_column("Field Path",    style="red",          no_wrap=True)
    t.add_column("Was Type",      style="bright_red",   justify="center")
    t.add_column("Before Value",  style="dim",          justify="left")
    for item in removed:
        t.add_row(item["field"], item["was_type"], item.get("before_value", "—"))
    return t


def _type_changed_table(type_changed: list[dict]) -> Table:
    t = Table(
        title="[bold yellow]Type Changes[/bold yellow]",
        box=box.ROUNDED,
        border_style="yellow",
        header_style="bold yellow",
        show_lines=True,
    )
    t.add_column("Field Path",    style="yellow",       no_wrap=True)
    t.add_column("Was",           style="bright_yellow", justify="center")
    t.add_column("Now",           style="bright_yellow", justify="center")
    t.add_column("Before → After", style="dim",         justify="left")
    for item in type_changed:
        before_after = f"{item.get('before_value','—')}  →  {item.get('after_value','—')}"
        t.add_row(item["field"], item["was"], item["now"], before_after)
    return t


def _score_bar(score: int, width: int = 20) -> str:
    """Return an ASCII progress bar for the drift score."""
    filled = round(score / 100 * width)
    bar    = "█" * filled + "░" * (width - filled)
    color  = "red" if score >= 50 else "yellow" if score >= 20 else "green"
    return f"[{color}]{bar}[/{color}] [bold]{score}/100[/bold]"


# ---------------------------------------------------------------------------
# Per-vendor report
# ---------------------------------------------------------------------------

def _report_vendor(vendor: dict) -> bool:
    """Print a formatted report for one vendor. Returns True if drift found."""
    name  = vendor["name"]
    desc  = vendor.get("description", "")
    score = vendor.get("drift_score", 0)

    console.rule(f"[bold cyan]{name}[/bold cyan]  [dim]{desc}[/dim]")

    if not vendor["has_drift"]:
        console.print("  [bold green][OK] No critical drift detected[/bold green]")
        console.print(f"  Drift score: {_score_bar(score)}\n")
        return False

    console.print("  [bold red][!!] DRIFT DETECTED -- parser may be broken[/bold red]")
    console.print(f"  Drift score: {_score_bar(score)}\n")

    if vendor["removed"]:
        console.print(_removed_table(vendor["removed"]))
        console.print()

    if vendor["type_changed"]:
        console.print(_type_changed_table(vendor["type_changed"]))
        console.print()

    if vendor["added"]:
        added_paths = ", ".join(item["field"] for item in vendor["added"])
        console.print(f"  [dim][i] Added (non-critical): {added_paths}[/dim]\n")

    return True


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    console.print()
    console.print(
        "[bold white on blue]  drift-watch v2 -- AI Vendor Schema Monitor  [/bold white on blue]"
    )
    console.print("[dim]Running full drift analysis across all vendors...[/dim]\n")

    report  = run_full_report()
    summary = report["summary"]

    any_drift = False
    for vendor in report["vendors"]:
        if _report_vendor(vendor):
            any_drift = True

    # Overall result
    console.rule("[bold white]OVERALL RESULT[/bold white]")
    console.print()
    console.print(
        f"  Vendors monitored : [bold]{summary['total_vendors']}[/bold]"
    )
    console.print(
        f"  Vendors with drift: [bold {'red' if any_drift else 'green'}]"
        f"{summary['vendors_with_drift']}[/bold {'red' if any_drift else 'green'}]"
    )
    console.print()

    if any_drift:
        console.print(
            "[bold red on dark_red]  RESULT: Critical drift found. Parsers need updating.  [/bold red on dark_red]"
        )
        console.print(
            "[dim]  Tip: run  python -m api.server  and open http://localhost:8000 for the visual dashboard[/dim]"
        )
        console.print()
        sys.stdout.flush()
        sys.exit(1)
    else:
        console.print(
            "[bold green on dark_green]  RESULT: All schemas stable.  [/bold green on dark_green]"
        )
        console.print()
        sys.stdout.flush()


if __name__ == "__main__":
    main()
