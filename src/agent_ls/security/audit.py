from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_ls.config.settings import get_settings
from agent_ls.security.allowlist import SecurityClassification


class AuditLogger:
    def __init__(self, log_path: Optional[str] = None):
        self._path = Path(log_path or get_settings().audit_log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log_command(
        self,
        command: str,
        classification: SecurityClassification,
        executed: bool,
        exit_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
        user_approved: Optional[bool] = None,
        reason: Optional[str] = None,
    ) -> None:
        entry: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "command": command,
            "classification": classification.value,
            "executed": executed,
        }
        if exit_code is not None:
            entry["exit_code"] = exit_code
        if duration_ms is not None:
            entry["duration_ms"] = duration_ms
        if user_approved is not None:
            entry["user_approved"] = user_approved
        if reason is not None:
            entry["reason"] = reason

        with open(self._path, "a") as f:
            f.write(json.dumps(entry) + "\n")


class ExecutionTimer:
    def __init__(self):
        self._start: float = 0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        pass

    @property
    def elapsed_ms(self) -> int:
        return int((time.perf_counter() - self._start) * 1000)
