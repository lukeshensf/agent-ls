import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(name="agent-ls", help="AI-powered developer environment setup agent")


@app.command()
def run(
    message: str = typer.Argument(None, help="Setup instruction to execute"),
    config: bool = typer.Option(False, "--config", help="Open configuration screen"),
    theme: Optional[str] = typer.Option(None, "--theme", help="UI theme (dark/light)"),
    resume: Optional[str] = typer.Option(None, "--resume", help="Resume a previous session by ID"),
):
    """Launch agent-ls TUI, optionally with an initial setup instruction."""
    from agent_ls.tui.app import AgentLSApp

    if theme:
        from agent_ls.config.settings import get_settings, save_settings

        settings = get_settings()
        settings.ui.theme = theme
        save_settings(settings)

    tui = AgentLSApp(initial_message=message, show_config=config, resume_session_id=resume)
    tui.run()


@app.command()
def setup(team: str = typer.Option(None, help="Team name to set up for")):
    """Run full developer environment setup for your team."""
    from agent_ls.tui.app import AgentLSApp

    msg = f"Set up my development environment for the {team} team" if team else "Set up my development environment"
    tui = AgentLSApp(initial_message=msg)
    tui.run()


@app.command()
def share(
    file_path: str = typer.Argument(help="Path to Obsidian markdown file"),
    channel: str = typer.Argument(help="Slack channel to share to (e.g., #team-eng)"),
):
    """Share an Obsidian document to a Slack channel."""
    from agent_ls.tui.app import AgentLSApp

    msg = f"Share {file_path} to {channel}"
    tui = AgentLSApp(initial_message=msg)
    tui.run()


@app.command()
def history():
    """List past sessions from ~/.agent-ls/sessions/."""
    from rich.console import Console

    console = Console()
    sessions_dir = Path.home() / ".agent-ls" / "sessions"

    if not sessions_dir.exists():
        console.print("[dim]No sessions directory found.[/]")
        return

    session_files = sorted(sessions_dir.iterdir(), reverse=True)

    if not session_files:
        console.print("[dim]No sessions found.[/]")
        return

    console.print("[bold]Past Sessions:[/]\n")
    for session_file in session_files:
        stat = session_file.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"  {session_file.name}  [dim]{modified}[/]")


@app.command()
def audit(
    n: int = typer.Option(20, "--last", "-n", help="Number of recent entries to show"),
):
    """Print the last N entries from the audit log."""
    from rich.console import Console
    from rich.table import Table

    from agent_ls.config.settings import get_settings

    console = Console()
    settings = get_settings()
    audit_path = Path(settings.audit_log_path)

    if not audit_path.exists():
        console.print("[dim]No audit log found.[/]")
        return

    try:
        lines = audit_path.read_text().strip().splitlines()
    except OSError as e:
        console.print(f"[red]Error reading audit log: {e}[/]")
        return

    if not lines:
        console.print("[dim]Audit log is empty.[/]")
        return

    entries = lines[-n:]

    table = Table(title="Audit Log")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Command")
    table.add_column("Classification")
    table.add_column("Exit Code", justify="right")
    table.add_column("Duration", justify="right")

    for line in entries:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        timestamp = entry.get("timestamp", "?")
        command = entry.get("command", "?")
        classification = entry.get("classification", "?")
        exit_code = str(entry.get("exit_code", "?"))
        duration = entry.get("duration_ms", entry.get("duration", "?"))
        duration_str = f"{duration}ms" if duration != "?" else "?"

        style_map = {
            "auto_approve": "green",
            "needs_approval": "yellow",
            "blocked": "red",
        }
        style = style_map.get(classification, None)

        table.add_row(timestamp, command, classification, exit_code, duration_str, style=style)

    console.print(table)


if __name__ == "__main__":
    app()
