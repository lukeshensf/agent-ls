from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import yaml


class DocTemplate(Enum):
    SETUP_GUIDE = "setup_guide"
    DAILY_LOG = "daily_log"
    DESIGN_DOC = "design_doc"
    RUNBOOK = "runbook"


@dataclass
class Frontmatter:
    title: str
    created: str = ""
    updated: str = ""
    tags: list[str] = field(default_factory=list)
    team: str = ""
    author: str = ""

    def __post_init__(self):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if not self.created:
            self.created = now
        if not self.updated:
            self.updated = now

    def to_yaml(self) -> str:
        data = {
            "title": self.title,
            "created": self.created,
            "updated": self.updated,
            "tags": self.tags,
        }
        if self.team:
            data["team"] = self.team
        if self.author:
            data["author"] = self.author
        return yaml.dump(data, default_flow_style=False, sort_keys=False).strip()

    @classmethod
    def from_yaml(cls, yaml_str: str) -> Frontmatter:
        data = yaml.safe_load(yaml_str)
        if not data:
            return cls(title="Untitled")
        return cls(
            title=data.get("title", "Untitled"),
            created=data.get("created", ""),
            updated=data.get("updated", ""),
            tags=data.get("tags", []),
            team=data.get("team", ""),
            author=data.get("author", ""),
        )


TEMPLATES = {
    DocTemplate.SETUP_GUIDE: """## Prerequisites

{prerequisites}

## Steps

{steps}

## Verification

{verification}

## Troubleshooting

{troubleshooting}
""",
    DocTemplate.DAILY_LOG: """## Summary

{summary}

## Steps Executed

{steps}

## Command Output

{output}
""",
    DocTemplate.DESIGN_DOC: """## Context

{context}

## Decision

{decision}

## Alternatives Considered

{alternatives}

## Consequences

{consequences}
""",
    DocTemplate.RUNBOOK: """## Overview

{overview}

## Steps

{steps}

## Rollback

{rollback}

## Contacts

{contacts}
""",
}


class TemplateEngine:
    def render(self, template: DocTemplate, context: dict) -> str:
        """Render a template with frontmatter and body content."""
        fm = Frontmatter(
            title=context.get("title", "Untitled"),
            tags=context.get("tags", []),
            team=context.get("team", ""),
            author=context.get("author", ""),
        )

        body = TEMPLATES[template]
        for key in _get_placeholders(body):
            body = body.replace(f"{{{key}}}", context.get(key, ""))

        return f"---\n{fm.to_yaml()}\n---\n\n# {fm.title}\n\n{body}"

    def parse_frontmatter(self, content: str) -> tuple[Frontmatter, str]:
        """Split a document into frontmatter and body."""
        if not content.startswith("---"):
            return Frontmatter(title="Untitled"), content

        parts = content.split("---", 2)
        if len(parts) < 3:
            return Frontmatter(title="Untitled"), content

        fm = Frontmatter.from_yaml(parts[1])
        body = parts[2].lstrip("\n")
        return fm, body


def _get_placeholders(template_str: str) -> list[str]:
    return re.findall(r"\{(\w+)\}", template_str)
