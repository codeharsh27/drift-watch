"""
main.py
-------
drift-watch CLI entrypoint.

Compares AI vendor response schemas and reports structural drift using
rich colored output. Exits with code 1 if any critical drift is detected --
suitable for use as a CI/CD gate.

Usage:
    python main.py
"""

import io
import json
import pathlib
import sys

# Force UTF-8 output on Windows so emoji / unicode render correctly
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer, encoding="utf-8", errors="replace"
    )

from rich.console import Console
from rich.table import Table
from rich import box

from core.differ import compare_shapes

# Use force_terminal so rich renders colour/markup in all Windows environments
console = Console(force_terminal=True, highlight=False)

# Root directory — fixtures/ lives next to main.py
ROOT = pathlib.Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures"

# ---------------------------------------------------------------------------
# Vendor definitions — each entry is (display_name, before_file, after_file)
# ---------------------------------------------------------------------------

VENDORS = [
    ("OpenAI",  "openai_before.json",  "openai_after.json"),
    ("Claude",  "claude_before.json",  "claude_after.json"),
    ("Cursor",  "cursor_before.json",  "cursor_after.json"),
]


def _load(filename: str) -> dict:
    return json.loads((FIXTURES / filename).read_text(encoding="utf-8"))


def _print_removed_table(removed: list[dict]) -> None:
    """Render a red table of removed fields."""
    table = Table(
        title="[bold red]Removed Fields (🚨 Critical)[/bold red]",
        box=box.ROUNDED,
        border_style="red",
        header_style="bold red",
        show_lines=True,
    )
    table.add_column("Field Path", style="red", no_wrap=True)
    table.add_column("Was Type", style="bright_red", justify="center")

    for item in removed:
        table.add_row(item["field"], item["was_type"])

    console.print(table)


def _print_type_changed_table(type_changed: list[dict]) -> None:
    """Render a yellow table of type-changed fields."""
    table = Table(
        title="[bold yellow]Type Changes (🚨 Critical)[/bold yellow]",
        box=box.ROUNDED,
        border_style="yellow",
        header_style="bold yellow",
        show_lines=True,
    )
    table.add_column("Field Path", style="yellow", no_wrap=True)
    table.add_column("Was", style="bright_yellow", justify="center")
    table.add_column("Now", style="bright_yellow", justify="center")

    for item in type_changed:
        table.add_row(item["field"], item["was"], item["now"])

    console.print(table)


def _report_vendor(name: str, before_file: str, after_file: str) -> bool:
    """Run drift detection for one vendor and print a formatted report.

    Returns True if critical drift was found, False otherwise.
    """
    console.rule(f"[bold cyan]{name}[/bold cyan]")

    before = _load(before_file)
    after  = _load(after_file)

    result = compare_shapes(before, after)

    if not result["has_drift"]:
        console.print("  [bold green][OK] No critical drift detected[/bold green]\n")
        return False

    # --- Critical drift ---
    console.print(
        "  [bold red][!!] DRIFT DETECTED -- parser may be broken[/bold red]\n"
    )

    if result["removed"]:
        _print_removed_table(result["removed"])
        console.print()

    if result["type_changed"]:
        _print_type_changed_table(result["type_changed"])
        console.print()

    if result["added"]:
        added_paths = ", ".join(item["field"] for item in result["added"])
        console.print(
            f"  [dim][i] Added fields (non-critical / growth): {added_paths}[/dim]\n"
        )

    return True


def main() -> None:
    console.print()
    console.print(
        "[bold white on blue]  drift-watch -- AI Vendor Schema Monitor  [/bold white on blue]"
    )
    console.print(
        "[dim]Comparing baseline fixtures against updated vendor responses...[/dim]\n"
    )

    any_drift = False

    for vendor_name, before_file, after_file in VENDORS:
        drift_found = _report_vendor(vendor_name, before_file, after_file)
        if drift_found:
            any_drift = True

    # ---------------------------------------------------------------------------
    # Overall result banner
    # ---------------------------------------------------------------------------
    console.rule("[bold white]OVERALL RESULT[/bold white]")
    console.print()

    if any_drift:
        console.print(
            "[bold red on dark_red]  RESULT: Critical drift found. Parsers need updating.  [/bold red on dark_red]"
        )
        console.print()
        # Flush before exit so rich buffer is written out
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
