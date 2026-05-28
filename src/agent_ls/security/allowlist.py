from __future__ import annotations

from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Optional

import yaml

from agent_ls.config.settings import get_settings


class SecurityClassification(Enum):
    AUTO_APPROVE = "auto_approve"
    NEEDS_APPROVAL = "needs_approval"
    BLOCKED = "blocked"


class AllowlistResult:
    def __init__(
        self,
        classification: SecurityClassification,
        risk: str = "unknown",
        reason: Optional[str] = None,
    ):
        self.classification = classification
        self.risk = risk
        self.reason = reason


class AllowlistChecker:
    def __init__(self, allowlist_path: Optional[str] = None):
        path = Path(allowlist_path or get_settings().allowlist_path)
        with open(path) as f:
            self._rules = yaml.safe_load(f)

    def classify(self, command: str) -> AllowlistResult:
        command = command.strip()

        for rule in self._rules.get("blocked", []):
            if fnmatch(command, rule["pattern"]):
                return AllowlistResult(
                    SecurityClassification.BLOCKED,
                    risk="critical",
                    reason=rule.get("reason", "Blocked by security policy"),
                )

        for rule in self._rules.get("require_approval", []):
            if fnmatch(command, rule["pattern"]):
                return AllowlistResult(
                    SecurityClassification.NEEDS_APPROVAL,
                    risk=rule.get("risk", "medium"),
                    reason=rule.get("reason"),
                )

        for rule in self._rules.get("auto_approve", []):
            if fnmatch(command, rule["pattern"]):
                return AllowlistResult(
                    SecurityClassification.AUTO_APPROVE,
                    risk=rule.get("risk", "low"),
                )

        return AllowlistResult(
            SecurityClassification.NEEDS_APPROVAL,
            risk="unknown",
            reason="Command not in allowlist",
        )
