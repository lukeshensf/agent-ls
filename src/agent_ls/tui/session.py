from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


SESSIONS_DIR = Path.home() / ".agent-ls" / "sessions"


@dataclass
class SessionSummary:
    session_id: str
    created_at: str
    updated_at: str
    original_message: str
    status: str
    step_count: int
    completed_count: int


class SessionManager:
    """Manages session persistence to disk as JSON files."""

    def __init__(self, sessions_dir: Path = SESSIONS_DIR) -> None:
        self._sessions_dir = sessions_dir

    def _ensure_dir(self) -> None:
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    def _session_path(self, session_id: str) -> Path:
        return self._sessions_dir / f"{session_id}.json"

    def save_checkpoint(
        self, session_id: str, state: dict, original_message: str
    ) -> None:
        """Serialize state to JSON and save to disk.

        For messages, stores just the content strings.
        Plan and execution_log are stored as lists of dicts.
        """
        self._ensure_dir()

        path = self._session_path(session_id)
        now = datetime.now(timezone.utc).isoformat()

        # Extract messages as plain content strings
        messages: list[str] = []
        for msg in state.get("messages", []):
            if hasattr(msg, "content"):
                messages.append(msg.content)
            elif isinstance(msg, str):
                messages.append(msg)

        # Extract plan as list of dicts
        plan: list[dict] = []
        for step in state.get("plan", []):
            if hasattr(step, "__dataclass_fields__"):
                plan.append(asdict(step))
            elif isinstance(step, dict):
                plan.append(step)

        # Extract execution_log as list of dicts
        execution_log: list[dict] = []
        for entry in state.get("execution_log", []):
            if hasattr(entry, "__dataclass_fields__"):
                execution_log.append(asdict(entry))
            elif isinstance(entry, dict):
                execution_log.append(entry)

        # Determine status
        error = state.get("error")
        if error:
            status = "failed"
        elif state.get("current_step", 0) >= len(plan) and plan:
            status = "completed"
        else:
            status = "interrupted"

        # Load existing to preserve created_at
        existing = self._load_raw(session_id)
        created_at = existing.get("created_at", now) if existing else now

        data = {
            "session_id": session_id,
            "created_at": created_at,
            "updated_at": now,
            "original_message": original_message,
            "status": status,
            "plan": plan,
            "current_step": state.get("current_step", 0),
            "execution_log": execution_log,
            "messages": messages,
        }

        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_session(self, session_id: str) -> Optional[dict]:
        """Load a session by ID, returning the raw dict or None."""
        return self._load_raw(session_id)

    def _load_raw(self, session_id: str) -> Optional[dict]:
        path = self._session_path(session_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

    def list_sessions(self) -> list[SessionSummary]:
        """List all sessions sorted by updated_at descending."""
        if not self._sessions_dir.exists():
            return []

        summaries: list[SessionSummary] = []
        for path in self._sessions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            plan = data.get("plan", [])
            step_count = len(plan)
            completed_count = sum(
                1 for step in plan if step.get("status") == "done"
            )

            summaries.append(
                SessionSummary(
                    session_id=data.get("session_id", path.stem),
                    created_at=data.get("created_at", ""),
                    updated_at=data.get("updated_at", ""),
                    original_message=data.get("original_message", ""),
                    status=data.get("status", "unknown"),
                    step_count=step_count,
                    completed_count=completed_count,
                )
            )

        summaries.sort(key=lambda s: s.updated_at, reverse=True)
        return summaries

    def cleanup_old(self, max_age_days: int = 7) -> None:
        """Remove session files older than max_age_days."""
        if not self._sessions_dir.exists():
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

        for path in self._sessions_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                # Remove unreadable files
                path.unlink(missing_ok=True)
                continue

            updated_at_str = data.get("updated_at", "")
            if not updated_at_str:
                path.unlink(missing_ok=True)
                continue

            try:
                updated_at = datetime.fromisoformat(updated_at_str)
                # Ensure timezone-aware comparison
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                if updated_at < cutoff:
                    path.unlink(missing_ok=True)
            except ValueError:
                path.unlink(missing_ok=True)
