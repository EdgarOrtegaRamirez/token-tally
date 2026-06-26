# Token Tally - AI Token Usage Tracker & Cost Analyzer
# SPDX-License-Identifier: MIT

"""CLI interface for token tally."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

import click
from rich.console import Console

from .analyzer import UsageAnalyzer
from .models import Provider
from .output import (
    console, print_cost, print_error, print_header,
    print_info, print_section, print_success, print_table,
    print_warning,
)
from .storage import TokenStorage


def get_storage(ctx: click.Context) -> TokenStorage:
    """Get storage instance from CLI context."""
    return ctx.ensure_object(dict).get("storage")


@click.group()
@click.option("--db-path", default=None, help="Path to SQLite database file")
@click.pass_context
def main(ctx: click.Context, db_path: Optional[str]):
    """Token Tally - Track AI token usage and costs across providers."""
    storage = TokenStorage(db_path)
    ctx.ensure_object(dict)["storage"] = storage
    ctx.ensure_object(dict)["analyzer"] = UsageAnalyzer(storage)


@main.command()
@click.option("--project", default="default", help="Project name")
@click.option("--session", default="default", help="Session identifier")
@click.option("--model", required=True, help="Model name (e.g., gpt-4o, claude-3.5-sonnet)")
@click.option("--provider", default="openai", help="Provider (openai, anthropic, google, groq, openrouter, local)")
@click.option("--input-tokens", required=True, type=int, help="Number of input tokens")
@click.option("--output-tokens", required=True, type=int, help="Number of output tokens")
@click.option("--duration", default=0.0, type=float, help="Request duration in seconds")
@click.option("--task-type", default="general", help="Task type (chat, code, summarization)")
@click.option("--prompt-template", default="", help="Prompt template name")
@click.option("--metadata", default=None, help="Additional metadata as JSON string")
@click.pass_context
def add(ctx: click.Context, project, session, model, provider, input_tokens, output_tokens, duration, task_type, prompt_template, metadata):
    """Record a new usage entry."""
    storage = get_storage(ctx)

    try:
        prov = Provider(provider)
    except ValueError:
        print_error(f"Invalid provider '{provider}'. Valid: {', '.join(p.value for p in Provider)}")
        ctx.exit(1)

    if input_tokens < 0:
        print_error("Input tokens cannot be negative")
        ctx.exit(1)
    if output_tokens < 0:
        print_error("Output tokens cannot be negative")
        ctx.exit(1)

    meta = {}
    if metadata:
        try:
            meta = json.loads(metadata)
        except json.JSONDecodeError as e:
            print_error(f"Invalid JSON metadata: {e}")
            ctx.exit(1)

    from .models import UsageEntry
    entry = UsageEntry(
        project=project, session=session, model=model, provider=prov,
        input_tokens=input_tokens, output_tokens=output_tokens,
        duration_seconds=duration, task_type=task_type,
        prompt_template=prompt_template, metadata=meta,
    )
    storage.add_entry(entry)

    console.print(f"\n[green]✓ Recorded usage for {model}[/green]")
    console.print(f"  Input tokens:  {input_tokens:,}")
    console.print(f"  Output tokens: {output_tokens:,}")
    console.print(f"  Total tokens:  {input_tokens + output_tokens:,}")
    console.print(f"  Estimated cost: {print_cost(entry.estimated_cost_usd)}")
    console.print(f"  Project: {project} | Session: {session}")

    # Check budget alerts
    analyzer = ctx.ensure_object(dict)["analyzer"]
    alerts = analyzer.get_budget_alerts()
    for alert in alerts:
        if alert["severity"] == "critical":
            print_warning(f"BUDGET ALERT: {alert['message']}")


@main.command()
@click.option("--project", default=None, help="Filter by project name")
@click.option("--model", default=None, help="Filter by model name")
@click.option("--provider", default=None, help="Filter by provider")
@click.option("--limit", default=20, type=int, help="Maximum entries to show")
@click.pass_context
def list(ctx: click.Context, project, model, provider, limit):
    """List recent usage entries."""
    storage = get_storage(ctx)

    prov = None
    if provider:
        try:
            prov = Provider(provider)
        except ValueError:
            print_error(f"Invalid provider '{provider}'")
            return

    entries = storage.get_entries(project=project, model=model, provider=prov, limit=limit)

    if not entries:
        print_info("No usage entries found.")
        return

    print_section("Recent Usage Entries")
    data = []
    for entry in entries:
        ts = entry.timestamp.strftime("%Y-%m-%d %H:%M")
        data.append({
            "Time": ts, "Project": entry.project, "Model": entry.model,
            "In": f"{entry.input_tokens:,}", "Out": f"{entry.output_tokens:,}",
            "Cost": print_cost(entry.estimated_cost_usd),
        })
    print_table(data, headers=["Time", "Project", "Model", "In", "Out", "Cost"])


@main.command()
@click.option("--project", default=None, help="Filter by project name")
@click.option("--provider", default=None, help="Filter by provider")
@click.pass_context
def summary(ctx: click.Context, project, provider):
    """Show cost summary and overview."""
    storage = get_storage(ctx)
    analyzer = ctx.ensure_object(dict)["analyzer"]

    overview = analyzer.get_overview()
    summary_data = storage.get_cost_summary(project=project)

    print_header("Token Usage Summary", f"{'For project: ' + project if project else 'All projects'}")
    console.print("[bold]Total Costs:[/bold]")
    console.print(f"  Total cost:        [bold]{print_cost(summary_data.total_cost_usd)}[/bold]")
    console.print(f"  Total requests:    {overview['total_requests']:,}")
    console.print(f"  Avg cost/request:  {summary_data.formatted_average_cost}")
    console.print()
    console.print("[bold]Token Counts:[/bold]")
    console.print(f"  Input tokens:      {overview['total_input']:,}")
    console.print(f"  Output tokens:     {overview['total_output']:,}")
    console.print(f"  Total tokens:      {overview['total_tokens']:,}")
    console.print()
    console.print("[bold]Recent Usage:[/bold]")
    console.print(f"  Last 7 days:       {overview['last_7_days_requests']} requests, {print_cost(overview['last_7_days_cost'])}")
    console.print(f"  Last 30 days:      {overview['last_30_days_requests']} requests, {print_cost(overview['last_30_days_cost'])}")
    console.print()

    if summary_data.model_breakdown:
        print_section("Cost by Model")
        model_data = analyzer.get_cost_breakdown(project=project)
        print_table(model_data, headers=["Model", "Tokens", "Cost", "Avg Cost/K"])


@main.command()
@click.option("--project", default=None, help="Filter by project name")
@click.pass_context
def models(ctx: click.Context, project):
    """List tracked models with usage stats."""
    storage = get_storage(ctx)
    models_list = storage.get_all_models()
    if not models_list:
        print_info("No models tracked yet.")
        return

    print_section("Tracked Models")
    analyzer = ctx.ensure_object(dict)["analyzer"]
    efficiency = analyzer.get_model_efficiency(project=project)
    print_table(efficiency, headers=["Model", "Requests", "Tokens", "Cost", "Avg Duration (s)", "Tokens/s", "Cost/K Tokens"])


@main.command()
@click.option("--project", default=None, help="Filter by project name")
@click.pass_context
def trends(ctx: click.Context, project):
    """Show usage trends and analysis."""
    storage = get_storage(ctx)
    analyzer = ctx.ensure_object(dict)["analyzer"]

    trend = analyzer.get_trend_analysis(days=30)
    print_section("Usage Trends (30 days)")
    if isinstance(trend, dict):
        console.print(f"  Trend direction: [bold]{trend['trend_direction']}[/bold]")
        console.print(f"  Cost change:     {trend['cost_change_pct']:+.1f}%")
    else:
        console.print("[yellow]Not enough data for trend analysis[/yellow]")

    print_section("Daily Breakdown (Last 14 days)")
    daily_stats = storage.get_daily_stats(days=30)
    if daily_stats:
        data = [{
            "Day": d["day"], "Tokens": f"{d['tokens']:,}",
            "Requests": str(d["requests"]), "Cost": print_cost(d["cost"]),
        } for d in daily_stats[:14]]
        print_table(data, headers=["Day", "Tokens", "Requests", "Cost"])

    spikes = analyzer.detect_spikes(project=project)
    if spikes:
        print_section("Usage Spikes Detected")
        spike_data = [{
            "Day": s["day"], "Tokens": f"{s['tokens']:,}",
            "Multiplier": f"{s['multiplier']}x", "Cost": print_cost(s["cost"]),
        } for s in spikes]
        print_table(spike_data, headers=["Day", "Tokens", "Multiplier", "Cost"])


@main.command()
@click.option("--daily-budget", default=5.0, type=float, help="Daily budget in USD")
@click.option("--monthly-budget", default=100.0, type=float, help="Monthly budget in USD")
@click.pass_context
def alerts(ctx: click.Context, daily_budget, monthly_budget):
    """Check for budget alerts and cost issues."""
    analyzer = ctx.ensure_object(dict)["analyzer"]
    alerts = analyzer.get_budget_alerts(daily_budget=daily_budget, monthly_budget=monthly_budget)

    if not alerts:
        print_success("No budget alerts. You're within budget!")
        return

    print_section("Budget Alerts")
    for alert in alerts:
        severity_icon = {"critical": "[red]🔴", "high": "[red]", "medium": "[yellow]🟡"}.get(alert["severity"], "")
        console.print(f"{severity_icon} [bold]{alert['type']}[/bold]: {alert['message']}")


@main.command()
@click.option("--project", default=None, help="Filter by project name")
@click.pass_context
def export(ctx: click.Context, project):
    """Export usage data as JSON."""
    storage = get_storage(ctx)
    entries = storage.get_entries(project=project, limit=10000, sort_order="asc")

    data = []
    for entry in entries:
        data.append({
            "id": entry.id, "timestamp": entry.timestamp.isoformat(),
            "project": entry.project, "session": entry.session,
            "model": entry.model, "provider": entry.provider.value,
            "input_tokens": entry.input_tokens, "output_tokens": entry.output_tokens,
            "total_tokens": entry.total_tokens,
            "estimated_cost_usd": entry.estimated_cost_usd,
            "task_type": entry.task_type,
            "duration_seconds": entry.duration_seconds,
        })
    click.echo(json.dumps(data, indent=2))


@main.command()
@click.option("--project", default=None, help="Clear a specific project. Omit to clear all.")
@click.pass_context
def clear(ctx: click.Context, project):
    """Clear usage entries."""
    storage = get_storage(ctx)
    if project:
        count = storage.clear_entries(project=project)
        print_success(f"Cleared {count} entries for project '{project}'")
    else:
        count = storage.clear_entries()
        print_success(f"Cleared {count} total entries")


@main.command()
@click.pass_context
def sample_config(ctx: click.Context):
    """Print a sample configuration file."""
    print_header("Sample Configuration")
    config = {
        "storage": {"db_path": str(__import__("pathlib").Path.home() / ".token_tally" / "tally.db")},
        "budget": {"daily": 5.0, "monthly": 100.0},
        "defaults": {"project": "default", "provider": "openai", "task_type": "general"},
    }
    click.echo(json.dumps(config, indent=2))


@main.command()
@click.pass_context
def version(ctx: click.Context):
    """Show version information."""
    from . import __version__
    console.print(f"Token Tally v{__version__}")
    console.print("AI Token Usage Tracker & Cost Analyzer")
    console.print("GitHub: https://github.com/EdgarOrtegaRamirez/token-tally")


if __name__ == "__main__":
    main()
