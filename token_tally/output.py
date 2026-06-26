# Token Tally - AI Token Usage Tracker & Cost Analyzer
# SPDX-License-Identifier: MIT

"""Rich text output helpers for the CLI."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

console = Console()
error_console = Console(stderr=True)


def print_header(title: str, subtitle: str = "") -> None:
    """Print a formatted header."""
    console.print()
    console.print(Panel(
        f"[bold]{title}[/bold]" + (f"\n{subtitle}" if subtitle else ""),
        box=box.ROUNDED, border_style="cyan",
    ))
    console.print()


def print_section(title: str) -> None:
    """Print a section header."""
    console.print(f"\n[bold cyan]{'─' * 40}[/bold cyan]")
    console.print(f"[bold cyan]{title}[/bold cyan]")
    console.print(f"[bold cyan]{'─' * 40}[/bold cyan]\n")


def print_table(data: list[dict], title: str = "", headers: list[str] = None) -> None:
    """Print a rich table."""
    if not data:
        console.print("[yellow]No data to display.[/yellow]")
        return
    table = Table(title=title, box=box.ROUNDED, show_header=True, header_style="bold cyan")
    keys = list(data[0].keys()) if not headers else headers
    for key in keys:
        table.add_column(key.replace("_", " ").title())
    for row in data:
        table.add_row(*[str(row.get(k, "")) for k in keys])
    console.print(table)


def print_cost(cost: float, prefix: str = "$") -> str:
    """Format a cost value for display."""
    if cost < 0.01:
        return f"{prefix}{cost * 100:.2f}¢"
    return f"{prefix}{cost:.2f}"


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓ {message}[/green]")


def print_error(message: str) -> None:
    """Print an error message."""
    error_console.print(f"[red]✗ {message}[/red]")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]⚠ {message}[/yellow]")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ {message}[/blue]")
