# Implementation Plan: Fix TUI/Config/Router MyPy Errors

**Deliverable**: 1.6 — Fix remaining mypy errors in TUI, config, and router modules  
**Date**: 2026-07-05  
**Status**: In Progress

## Overview

Fix 14 mypy type errors across 5 files to achieve full type safety without weakening checks or using `# type: ignore`.

## Current State

**Baseline**:
- 223 tests passing
- 14 mypy errors across 5 files

**MyPy Errors**:
```
src/agent_ls/integrations/slack/client.py:37: error: Incompatible return value type (got "dict[Any, Any] | bytes", expected "dict[Any, Any]")
src/agent_ls/tui/screens/config.py:160: error: Argument "models" to "Settings" has incompatible type "dict[str, str]"; expected "ModelSettings"
src/agent_ls/tui/screens/config.py:165: error: Argument "ollama" to "Settings" has incompatible type "dict[str, str]"; expected "OllamaSettings"
src/agent_ls/tui/screens/config.py:168: error: Argument "slack" to "Settings" has incompatible type "dict[str, str | None]"; expected "SlackSettings"
src/agent_ls/tui/screens/config.py:171: error: Argument "obsidian" to "Settings" has incompatible type "dict[str, bool | str | None]"; expected "ObsidianSettings"
src/agent_ls/tui/screens/config.py:175: error: Argument "ui" to "Settings" has incompatible type "dict[str, bool | Any | NoSelection]"; expected "UISettings"
src/agent_ls/tui/screens/audit_viewer.py:103: error: "Row" has no attribute "style"
src/agent_ls/integrations/models/router.py:157: error: Unexpected keyword argument "model" for "ChatAnthropic"
src/agent_ls/integrations/models/router.py:163: error: Cannot find implementation or library stub for module named "langchain_ollama"
src/agent_ls/integrations/models/router.py:181: error: Skipping analyzing "boto3": module is installed, but missing library stubs or py.typed marker
src/agent_ls/integrations/models/router.py:182: error: Skipping analyzing "botocore": module is installed, but missing library stubs or py.typed marker
src/agent_ls/integrations/models/router.py:183: error: Skipping analyzing "botocore.config": module is installed, but missing library stubs or py.typed marker
src/agent_ls/tui/app.py:99: error: Argument 1 to "load_session" of "SessionManager" has incompatible type "str | None"; expected "str"
src/agent_ls/tui/app.py:198: error: Incompatible types in assignment (expression has type "GraphRunner", variable has type "None")
```

## Implementation Tasks

### Task 1: Fix Slack client return type
**File**: `src/agent_ls/integrations/slack/client.py`
**Error**: Line 37 - return type mismatch

**Root Cause**: `response.data` can be `dict[Any, Any] | bytes`, but return type declares only `dict[Any, Any]`

**Fix**:
- Add explicit type cast or type assertion to ensure we only return dict
- Slack API `chat_postMessage` always returns dict, so cast is safe

**Test Strategy**:
- Run existing slack client tests
- Verify no behavioral change

### Task 2: Fix config screen Settings construction
**File**: `src/agent_ls/tui/screens/config.py`
**Errors**: Lines 160, 165, 168, 171, 175 - passing dicts instead of typed settings objects

**Root Cause**: Creating `Settings` with raw dicts instead of proper Pydantic model instances

**Fix**:
- Change from `models={"cheap": ...}` to `models=ModelSettings(cheap=...)`
- Do same for `OllamaSettings`, `SlackSettings`, `ObsidianSettings`, `UISettings`

**Test Strategy**:
- Run TUI config tests
- Verify Settings object is correctly constructed
- No behavioral change expected

### Task 3: Fix audit viewer Row.style attribute
**File**: `src/agent_ls/tui/screens/audit_viewer.py`
**Error**: Line 103 - Row has no attribute "style"

**Root Cause**: Textual DataTable Row doesn't have a direct `style` attribute in the version we're using

**Fix**:
- Use Textual's correct API for styling rows
- Check DataTable.update_cell or row-level styling APIs
- May need to set style at cell level or use different approach

**Test Strategy**:
- Run audit viewer tests
- Verify row styling still works visually
- Check if there are integration tests for audit viewer

### Task 4: Fix router ChatAnthropic parameter
**File**: `src/agent_ls/integrations/models/router.py`
**Error**: Line 157 - unexpected keyword argument "model"

**Root Cause**: ChatAnthropic expects `model_name` parameter, not `model`

**Fix**:
- Change `ChatAnthropic(model=model_name)` to `ChatAnthropic(model_name=model_name)`

**Test Strategy**:
- Run model router tests
- Verify anthropic provider still works

### Task 5: Add type stubs configuration for router imports
**File**: `src/agent_ls/integrations/models/router.py`
**Errors**: Lines 163, 181-183 - missing stubs for langchain_ollama, boto3, botocore

**Root Cause**: Third-party libraries don't have type stubs

**Fix Options**:
1. Add `# type: ignore[import-untyped]` for these specific imports (acceptable for 3rd party libs)
2. Install types-boto3 and types-botocore if available
3. Check if langchain_ollama has stubs

**Decision**: Use targeted type ignores for unavailable stubs (3rd party, not our code)

**Test Strategy**:
- Run model router tests
- Verify all providers still work

### Task 6: Fix app.py load_session null check
**File**: `src/agent_ls/tui/app.py`
**Error**: Line 99 - passing Optional[str] to function expecting str

**Root Cause**: `self._resume_session_id` is `Optional[str]`, but `load_session` expects non-None

**Fix**:
- Add null check before calling `load_session`
- The None case is already handled by caller logic, just need explicit check

**Test Strategy**:
- Run TUI app tests
- Verify session resume still works

### Task 7: Fix app.py GraphRunner type assignment
**File**: `src/agent_ls/tui/app.py`
**Error**: Line 198 - assigning GraphRunner to None-typed variable

**Root Cause**: `self._graph_runner` declared as `None` (line 63), but assigned `GraphRunner` instance

**Fix**:
- Change declaration to `self._graph_runner: Optional[GraphRunner] = None`
- Add import for GraphRunner type (use TYPE_CHECKING to avoid circular import)

**Test Strategy**:
- Run TUI app tests
- Verify graph execution still works

## Quality Gates

Before opening PR:
```bash
# All must pass:
.venv/bin/python -m pytest -q                 # 223 tests must pass
.venv/bin/ruff check src/ tests/              # No linting errors
.venv/bin/mypy src/                           # Zero mypy errors
```

## Constraints

- NEVER delete or skip existing tests
- NEVER weaken security gates
- NEVER use `# type: ignore` except for unavoidable 3rd-party library stubs
- Keep changes minimal and scoped
- Follow existing architecture patterns

## Success Criteria

- All 223 tests pass
- Zero mypy errors
- No ruff violations
- No behavioral changes
- PR approved and merged

## Rollback Plan

If any test failures occur:
1. Git revert the commit
2. Re-analyze the specific test failure
3. Fix with more targeted approach
