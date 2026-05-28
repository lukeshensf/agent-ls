from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SlashCommand:
    name: str
    args: list[str]


# Maps command name -> tuple of expected argument names (for documentation/validation)
COMMANDS: dict[str, tuple[str, ...]] = {
    "share": ("format",),
    "update-kb": ("path",),
    "config": ("key", "value"),
    "history": (),
    "audit": ("filter",),
    "theme": ("name",),
}


def parse_slash_command(text: str) -> SlashCommand | None:
    """Parse a slash command from user input.

    Returns None if the text is not a slash command.
    Returns a SlashCommand if valid.
    Raises ValueError if the command name is not recognized.
    """
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None

    parts = stripped.split()
    command_name = parts[0][1:]  # Remove the leading '/'

    if not command_name:
        return None

    if command_name not in COMMANDS:
        available = ", ".join(f"/{cmd}" for cmd in sorted(COMMANDS))
        raise ValueError(
            f"Unknown command '/{command_name}'. Available commands: {available}"
        )

    args = parts[1:]
    return SlashCommand(name=command_name, args=args)


def get_command_help() -> str:
    """Return formatted help text listing all available slash commands."""
    lines: list[str] = ["Available commands:", ""]

    descriptions: dict[str, str] = {
        "share": "Share the current session (format: markdown|json)",
        "update-kb": "Update the knowledge base from a path",
        "config": "View or set configuration (key [value])",
        "history": "Show session history",
        "audit": "Show audit log (optional filter)",
        "theme": "Switch theme (name: dark|light)",
    }

    for cmd in sorted(COMMANDS):
        arg_spec = COMMANDS[cmd]
        arg_str = " ".join(f"<{a}>" for a in arg_spec) if arg_spec else ""
        usage = f"/{cmd} {arg_str}".strip()
        desc = descriptions.get(cmd, "")
        lines.append(f"  {usage:<25} {desc}")

    return "\n".join(lines)
