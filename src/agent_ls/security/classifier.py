from __future__ import annotations

import re


def _normalize_whitespace(command: str) -> str:
    """Normalize all whitespace to single spaces for reliable pattern matching.

    Collapses tabs, newlines, and multiple spaces to single spaces so evasive
    spacing (e.g., `sudo\trm`, `rm  -rf`) doesn't bypass detection. Does NOT
    alter the logical content, just standardizes whitespace.

    Args:
        command: Raw command string

    Returns:
        Command with normalized whitespace

    Example:
        >>> _normalize_whitespace("sudo\trm -rf /")
        'sudo rm -rf /'
        >>> _normalize_whitespace("rm  -rf")
        'rm -rf'
    """
    return re.sub(r'\s+', ' ', command)


PIPE_TO_SHELL = re.compile(r"\|\s*(ba)?sh\b", re.IGNORECASE)
REDIRECT_TO_SYSTEM = re.compile(r">\s*/etc/", re.IGNORECASE)
SUBSHELL_SUDO = re.compile(r"\$\(.*sudo.*\)", re.IGNORECASE)


def has_pipe_to_shell(command: str) -> bool:
    normalized = _normalize_whitespace(command)
    return bool(PIPE_TO_SHELL.search(normalized))


def has_system_redirect(command: str) -> bool:
    normalized = _normalize_whitespace(command)
    return bool(REDIRECT_TO_SYSTEM.search(normalized))


def has_subshell_escalation(command: str) -> bool:
    normalized = _normalize_whitespace(command)
    return bool(SUBSHELL_SUDO.search(normalized))


def compute_risk_score(command: str) -> int:
    """Return a risk score 0-100 for a command based on heuristics."""
    score = 0
    normalized = _normalize_whitespace(command).lower()

    if "sudo" in normalized:
        score += 40
    if "rm " in normalized:
        score += 20
    if "-rf" in normalized or "-r -f" in normalized:
        score += 30
    if has_pipe_to_shell(command):
        score += 50
    if has_system_redirect(command):
        score += 40
    if has_subshell_escalation(command):
        score += 60
    if "/etc/" in normalized or "/system/" in normalized:
        score += 30
    return min(score, 100)
