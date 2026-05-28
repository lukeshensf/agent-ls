from __future__ import annotations

import re


PIPE_TO_SHELL = re.compile(r".*\|\s*(ba)?sh\b")
REDIRECT_TO_SYSTEM = re.compile(r".*>\s*/etc/")
SUBSHELL_SUDO = re.compile(r".*\$\(.*sudo.*\)")


def has_pipe_to_shell(command: str) -> bool:
    return bool(PIPE_TO_SHELL.match(command))


def has_system_redirect(command: str) -> bool:
    return bool(REDIRECT_TO_SYSTEM.match(command))


def has_subshell_escalation(command: str) -> bool:
    return bool(SUBSHELL_SUDO.match(command))


def compute_risk_score(command: str) -> int:
    """Return a risk score 0-100 for a command based on heuristics."""
    score = 0
    if "sudo" in command:
        score += 40
    if "rm " in command:
        score += 20
    if "-rf" in command:
        score += 30
    if has_pipe_to_shell(command):
        score += 50
    if has_system_redirect(command):
        score += 40
    if has_subshell_escalation(command):
        score += 60
    if "/etc/" in command or "/System/" in command:
        score += 30
    return min(score, 100)
