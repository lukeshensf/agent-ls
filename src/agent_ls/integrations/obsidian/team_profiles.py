from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import yaml

from agent_ls.graph.state import PlanStep
from agent_ls.integrations.obsidian.vault import ObsidianVault


@dataclass
class TeamProfile:
    name: str
    description: str = ""
    required_tools: list[str] = field(default_factory=list)
    optional_tools: list[str] = field(default_factory=list)
    setup_steps: list[PlanStep] = field(default_factory=list)
    channels: list[str] = field(default_factory=list)


class TeamProfileLoader:
    def __init__(self, vault: Optional[ObsidianVault] = None):
        self._vault = vault or ObsidianVault()

    def load_profile(self, team_name: str) -> Optional[TeamProfile]:
        """Load a team profile from the vault."""
        profile_path = f"teams/{team_name}/profile.md"
        if not self._vault.exists(profile_path):
            return None

        content = self._vault.read(profile_path)
        return self._parse_profile(team_name, content)

    def list_profiles(self) -> list[str]:
        """List available team profile names."""
        docs = self._vault.list_docs("teams")
        teams = set()
        for doc in docs:
            parts = doc.split("/")
            if len(parts) >= 2 and parts[-1] == "profile.md":
                teams.add(parts[-2] if parts[0] == "teams" else parts[0])
        return sorted(teams)

    def _parse_profile(self, team_name: str, content: str) -> TeamProfile:
        """Parse a profile markdown file with YAML frontmatter."""
        if not content.startswith("---"):
            return TeamProfile(name=team_name)

        parts = content.split("---", 2)
        if len(parts) < 3:
            return TeamProfile(name=team_name)

        try:
            data = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            return TeamProfile(name=team_name)

        if not isinstance(data, dict):
            return TeamProfile(name=team_name)

        steps = []
        for step in data.get("setup_steps", []):
            if isinstance(step, dict):
                steps.append(
                    PlanStep(
                        description=step.get("description", ""),
                        command=step.get("command"),
                    )
                )

        return TeamProfile(
            name=team_name,
            description=data.get("description", ""),
            required_tools=data.get("required_tools", []),
            optional_tools=data.get("optional_tools", []),
            setup_steps=steps,
            channels=data.get("channels", []),
        )
