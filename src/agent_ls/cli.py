import typer

app = typer.Typer(name="agent-ls", help="AI-powered developer environment setup agent")


@app.command()
def run(
    message: str = typer.Argument(None, help="Setup instruction to execute"),
    config: bool = typer.Option(False, "--config", help="Open configuration screen"),
):
    """Launch agent-ls TUI, optionally with an initial setup instruction."""
    from agent_ls.tui.app import AgentLSApp

    tui = AgentLSApp(initial_message=message, show_config=config)
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


if __name__ == "__main__":
    app()
