from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from agent_ls.config.settings import get_settings

_GENERALIZABLE_COMMANDS = [
    ("npm install -g", "npm install -g *"),
    ("brew install", "brew install *"),
    ("brew tap", "brew tap *"),
    ("pip install", "pip install *"),
    ("pip3 install", "pip3 install *"),
    ("npm install", "npm install *"),
    ("cargo install", "cargo install *"),
    ("gem install", "gem install *"),
    ("nvm install", "nvm install *"),
    ("nvm use", "nvm use *"),
    ("git clone", "git clone *"),
]


class DynamicAllowlist:
    def __init__(self, persistent_path: Optional[Path] = None):
        config_dir = Path(get_settings().audit_log_path).parent
        self._path = persistent_path or (config_dir / "approved_patterns.yaml")

    def add_approved_pattern(self, command: str) -> str:
        """Generalize a command into a glob pattern and persist it."""
        pattern = self._generalize(command)

        rules = self.load_dynamic_rules()
        existing_patterns = {r["pattern"] for r in rules}
        if pattern in existing_patterns:
            return pattern

        rules.append({
            "pattern": pattern,
            "risk": "low",
            "reason": "User-approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "original_command": command,
        })

        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            yaml.dump(rules, f, default_flow_style=False)

        return pattern

    def load_dynamic_rules(self) -> list[dict]:
        """Load user-approved patterns from persistent storage."""
        if not self._path.exists():
            return []
        with open(self._path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, list) else []

    def _generalize(self, command: str) -> str:
        """Convert a specific command into a glob pattern."""
        for prefix, pattern in _GENERALIZABLE_COMMANDS:
            if command.startswith(prefix):
                return pattern

        parts = command.split()
        if len(parts) >= 2:
            return f"{parts[0]} *"

        return command
