from __future__ import annotations

import re
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


# Higher rank == more restrictive. Used to pick the worst result across a chained
# command's segments, so a permissive head can never override a dangerous tail.
_RESTRICTION_RANK = {
    SecurityClassification.AUTO_APPROVE: 0,
    SecurityClassification.NEEDS_APPROVAL: 1,
    SecurityClassification.BLOCKED: 2,
}

# Shell operators that chain independent commands. Longer operators (`&&`, `||`)
# are listed before their single-character prefixes so the alternation prefers them.
_CHAIN_OPERATOR_RE = re.compile(r"\|\||&&|[;|&\n]")


def _split_segments(command: str) -> list[str]:
    """Split a command line into the independent commands a shell would run.

    Splitting on `;`, `&&`, `||`, `|`, `&`, and newline lets each segment be
    classified on its own, so `brew install x && rm -rf ~` no longer inherits the
    auto-approve verdict of its `brew install` head. Empty fragments are dropped.
    """
    return [seg.strip() for seg in _CHAIN_OPERATOR_RE.split(command) if seg.strip()]


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
        """Classify a command line, returning the most-restrictive verdict.

        The whole line is classified first (so legitimate rules whose patterns
        contain shell operators — e.g. `curl * | sh` or the fork-bomb signature —
        still match), then each chained segment is classified independently. The
        worst (most restrictive) result across all of them wins, so an auto-approved
        head can never smuggle a blocked/approval-needed tail past the gate.
        """
        command = command.strip()

        worst = self._classify_one(command)
        if _RESTRICTION_RANK[worst.classification] == max(_RESTRICTION_RANK.values()):
            return worst

        segments = _split_segments(command)
        # A single segment equal to the whole line adds nothing beyond `worst`.
        if len(segments) <= 1:
            return worst

        for segment in segments:
            result = self._classify_one(segment)
            if _RESTRICTION_RANK[result.classification] > _RESTRICTION_RANK[worst.classification]:
                worst = result
                if _RESTRICTION_RANK[worst.classification] == max(_RESTRICTION_RANK.values()):
                    break

        return worst

    def _classify_one(self, command: str) -> AllowlistResult:
        """Classify a single command string against the rule lists (no chain splitting)."""
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
