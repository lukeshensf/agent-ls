"""Type safety tests for audit.py.

This test module ensures the AuditLogger.log_command method
correctly handles all field types (bool, str, int) without
mypy type inference errors.
"""
import json
import subprocess

from agent_ls.security.audit import AuditLogger
from agent_ls.security.allowlist import SecurityClassification


class TestAuditLoggerTypes:
    """Test that AuditLogger handles all field types correctly."""

    def test_log_command_with_exit_code(self, tmp_path):
        """Test that exit_code (int) can be assigned without type errors."""
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_command(
            command="ls -la",
            classification=SecurityClassification.AUTO_APPROVE,
            executed=True,
            exit_code=0,
        )

        # Verify the log entry was written correctly
        with open(log_file) as f:
            entry = json.loads(f.read().strip())
            assert entry["exit_code"] == 0
            assert isinstance(entry["exit_code"], int)

    def test_log_command_with_duration_ms(self, tmp_path):
        """Test that duration_ms (int) can be assigned without type errors."""
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_command(
            command="sleep 1",
            classification=SecurityClassification.AUTO_APPROVE,
            executed=True,
            duration_ms=1500,
        )

        with open(log_file) as f:
            entry = json.loads(f.read().strip())
            assert entry["duration_ms"] == 1500
            assert isinstance(entry["duration_ms"], int)

    def test_log_command_with_all_int_fields(self, tmp_path):
        """Test that both exit_code and duration_ms can be set together."""
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_command(
            command="echo test",
            classification=SecurityClassification.AUTO_APPROVE,
            executed=True,
            exit_code=0,
            duration_ms=42,
        )

        with open(log_file) as f:
            entry = json.loads(f.read().strip())
            assert entry["exit_code"] == 0
            assert entry["duration_ms"] == 42
            assert isinstance(entry["exit_code"], int)
            assert isinstance(entry["duration_ms"], int)

    def test_log_command_with_user_approved(self, tmp_path):
        """Test that user_approved (bool) works correctly."""
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_command(
            command="sudo apt update",
            classification=SecurityClassification.NEEDS_APPROVAL,
            executed=True,
            user_approved=True,
        )

        with open(log_file) as f:
            entry = json.loads(f.read().strip())
            assert entry["user_approved"] is True
            assert isinstance(entry["user_approved"], bool)

    def test_log_command_with_reason(self, tmp_path):
        """Test that reason (str) works correctly."""
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_command(
            command="rm -rf /tmp/test",
            classification=SecurityClassification.BLOCKED,
            executed=False,
            reason="Dangerous operation blocked",
        )

        with open(log_file) as f:
            entry = json.loads(f.read().strip())
            assert entry["reason"] == "Dangerous operation blocked"
            assert isinstance(entry["reason"], str)

    def test_log_command_with_all_fields(self, tmp_path):
        """Test all optional fields together (bool, str, int)."""
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_command(
            command="git push origin main",
            classification=SecurityClassification.NEEDS_APPROVAL,
            executed=True,
            exit_code=0,
            duration_ms=2500,
            user_approved=True,
            reason="User confirmed push to main",
        )

        with open(log_file) as f:
            entry = json.loads(f.read().strip())
            assert entry["exit_code"] == 0
            assert entry["duration_ms"] == 2500
            assert entry["user_approved"] is True
            assert entry["reason"] == "User confirmed push to main"

    def test_log_command_minimal_fields(self, tmp_path):
        """Test with only required fields (no optional fields)."""
        log_file = tmp_path / "audit.log"
        logger = AuditLogger(log_path=str(log_file))

        logger.log_command(
            command="pwd",
            classification=SecurityClassification.AUTO_APPROVE,
            executed=True,
        )

        with open(log_file) as f:
            entry = json.loads(f.read().strip())
            assert "exit_code" not in entry
            assert "duration_ms" not in entry
            assert "user_approved" not in entry
            assert "reason" not in entry
            assert entry["command"] == "pwd"
            assert entry["executed"] is True


class TestMypyAuditFile:
    """Test that audit.py has no mypy errors."""

    def test_mypy_audit_file_zero_errors(self):
        """Verify that mypy reports 0 errors for audit.py."""
        result = subprocess.run(
            ["uv", "run", "mypy", "src/agent_ls/security/audit.py"],
            capture_output=True,
            text=True,
        )

        # Check that mypy found 0 errors
        assert "Found 0 errors" in result.stdout or result.returncode == 0, (
            f"Expected 0 mypy errors in audit.py, but got:\n{result.stdout}\n{result.stderr}"
        )
