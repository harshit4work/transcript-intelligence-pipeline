#!/usr/bin/env python3
"""
Transcript Intelligence Pipeline — CLI.

Usage:
    python cli.py list
    python cli.py process sample_data/transcripts/interview_01_pm_tool_onboarding.txt
    python cli.py process-all
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from tip.config import SAMPLE_TRANSCRIPTS_DIR, get_settings
from tip.pipeline import run_pipeline

console = Console()


def _mode_banner():
    settings = get_settings()
    mode_label = (
        "[bold green]LIVE[/bold green] (real Whisper + GPT-4 + Notion calls)"
        if settings.mode == "live"
        else "[bold yellow]MOCK[/bold yellow] (cached demo responses, zero API calls)"
    )
    console.print(Panel(f"Transcript Intelligence Pipeline — mode: {mode_label}", expand=False))


@click.group()
def cli():
    """Transcript Intelligence Pipeline CLI."""


@cli.command("list")
def list_samples():
    """List bundled sample transcripts."""
    _mode_banner()
    table = Table(title="Sample transcripts")
    table.add_column("Interview ID")
    table.add_column("File")
    for path in sorted(SAMPLE_TRANSCRIPTS_DIR.glob("*.txt")):
        table.add_row(path.stem, str(path))
    console.print(table)


@cli.command("process")
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--no-notion", is_flag=True, help="Skip the Notion sync step.")
def process(input_path: str, no_notion: bool):
    """Run the full pipeline on a single transcript (or audio file in LIVE mode)."""
    _mode_banner()

    def on_progress(stage: str, message: str):
        console.print(f"[cyan]\\[{stage}][/cyan] {message}")

    with console.status("Running pipeline...", spinner="dots"):
        output = run_pipeline(input_path, push_notion=not no_notion, on_progress=on_progress)

    _render_result(output)


@cli.command("process-all")
@click.option("--no-notion", is_flag=True, help="Skip the Notion sync step.")
def process_all(no_notion: bool):
    """Run the pipeline across every bundled sample transcript."""
    _mode_banner()
    files = sorted(SAMPLE_TRANSCRIPTS_DIR.glob("*.txt"))
    for path in files:
        console.rule(f"[bold]{path.stem}[/bold]")

        def on_progress(stage: str, message: str):
            console.print(f"[cyan]\\[{stage}][/cyan] {message}")

        output = run_pipeline(path, push_notion=not no_notion, on_progress=on_progress)
        _render_result(output, compact=True)
    console.rule("[bold green]Done[/bold green]")


def _render_result(output, compact: bool = False):
    r = output.extraction
    table = Table(title=f"Extraction summary — {r.interview_id}")
    table.add_column("Themes", justify="right")
    table.add_column("Pain Points", justify="right")
    table.add_column("Action Items", justify="right")
    table.add_column("Entities", justify="right")
    table.add_column("Method")
    table.add_column("Confidence", justify="right")
    table.add_row(
        str(len(r.themes)), str(len(r.pain_points)), str(len(r.action_items)),
        str(len(r.entities)), r.extraction_method.value, f"{r.confidence:.2f}",
    )
    console.print(table)

    if not compact:
        pt = Table(title="Pain points")
        pt.add_column("Severity")
        pt.add_column("Area")
        pt.add_column("Description")
        for p in r.pain_points:
            color = {"high": "red", "medium": "yellow", "low": "dim"}[p.severity.value]
            pt.add_row(f"[{color}]{p.severity.value.upper()}[/{color}]", p.affected_area, p.description)
        console.print(pt)

        at = Table(title="Action items")
        at.add_column("Priority")
        at.add_column("Owner")
        at.add_column("Action")
        for a in r.action_items:
            color = {"high": "red", "medium": "yellow", "low": "dim"}[a.priority.value]
            at.add_row(f"[{color}]{a.priority.value.upper()}[/{color}]", a.owner_hint or "-", a.action)
        console.print(at)

    console.print(f"[dim]JSON:[/dim] {output.json_path}")
    console.print(f"[dim]Notion markdown:[/dim] {output.notion_markdown_path}")
    if output.notion_destination:
        console.print(f"[dim]Notion sync:[/dim] {output.notion_destination}")
    console.print()


if __name__ == "__main__":
    cli()
