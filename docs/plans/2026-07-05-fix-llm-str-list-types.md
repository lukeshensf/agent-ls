# Implementation Plan: Fix LLM Response `str | list` Type Errors

**Deliverable:** PLAN.md 1.5  
**Date:** 2026-07-05  
**Status:** Ready for implementation

## Summary

LangChain's message `.content` field is typed as `str | list[str | dict]` to support both simple text responses and multi-part content (e.g., text + images). Currently, 6 graph nodes treat this field as a plain `str`, calling methods like `.strip()` or passing it to `json.loads()`, which causes mypy type errors.

This plan introduces a small shared helper function `_message_content_as_text(content) -> str` in a new `src/agent_ls/graph/utils.py` module that safely coerces list-of-parts content to a string. All 6 affected call sites will be updated to use this helper, eliminating the type errors while maintaining runtime behavior.

## Problem Statement

### Current mypy errors (6 total across 5 files):

1. **router.py:34** - `response.content.strip()` fails when content is a list
2. **router.py:42** - `re.search(last_message.content)` fails when content is a list
3. **plan.py:44** - `last_message.content + "\n\n..."` fails when content is a list
4. **plan.py:52** - `json.loads(response.content)` requires str|bytes, not list
5. **extract.py:47** - `json.loads(response.content)` requires str|bytes, not list
6. **error_recovery.py:55** - `json.loads(response.content)` requires str|bytes, not list
7. **context_gather.py:45** - `json.loads(response.content)` requires str|bytes, not list
8. **search.py:29** - `response.content.strip()` fails when content is a list

### Root cause

LangChain supports multi-modal responses where `.content` can be:
- `str` - simple text response (most common)
- `list[str | dict]` - multi-part content (text blocks, images, etc.)

For this project's use case (text-only LLM responses), the content will always be a string at runtime. However, mypy requires us to handle the union type properly.

## Solution Approach

### 1. Create a shared utility module

**File:** `src/agent_ls/graph/utils.py`

```python
"""Utility functions for graph node operations."""

from __future__ import annotations


def message_content_as_text(content: str | list[str | dict]) -> str:
    """Convert LangChain message content to plain text.
    
    LangChain's BaseMessage.content is typed as `str | list[str | dict]`
    to support multi-modal responses (text + images, etc.). For text-only
    LLM responses, content is always a str at runtime.
    
    This helper safely handles both cases:
    - If content is already a str, return as-is
    - If content is a list, join string parts with newlines
    
    Args:
        content: Message content from a LangChain message
        
    Returns:
        Plain text string representation of the content
        
    Example:
        >>> message_content_as_text("hello")
        'hello'
        >>> message_content_as_text(["hello", "world"])
        'hello\\nworld'
        >>> message_content_as_text([{"type": "text", "text": "hi"}, "bye"])
        'hi\\nbye'
    """
    if isinstance(content, str):
        return content
    
    # Handle list of mixed str and dict parts
    parts = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and "text" in item:
            # Multi-modal content block with text field
            parts.append(str(item["text"]))
        else:
            # Other dict formats - convert to string
            parts.append(str(item))
    
    return "\n".join(parts)
```

### 2. Update all affected files

Each file needs two changes:
1. Import the helper: `from agent_ls.graph.utils import message_content_as_text`
2. Wrap `.content` access: `message_content_as_text(response.content)`

**Files to modify (in order):**

1. `src/agent_ls/graph/router.py` (2 errors)
2. `src/agent_ls/graph/nodes/plan.py` (2 errors)
3. `src/agent_ls/graph/nodes/extract.py` (1 error)
4. `src/agent_ls/graph/nodes/error_recovery.py` (1 error)
5. `src/agent_ls/graph/nodes/context_gather.py` (1 error)
6. `src/agent_ls/graph/nodes/search.py` (1 error)

## Files to Change

### 1. `src/agent_ls/graph/utils.py` (NEW FILE)
- Create new module with `message_content_as_text()` helper
- Comprehensive docstring with examples
- Handle both `str` and `list[str | dict]` cases

### 2. `src/agent_ls/graph/router.py`
- **Line 34:** Change `response.content.strip()` to `message_content_as_text(response.content).strip()`
- **Line 42:** Change `_CHANNEL_PATTERN.search(last_message.content)` to `_CHANNEL_PATTERN.search(message_content_as_text(last_message.content))`
- Add import: `from agent_ls.graph.utils import message_content_as_text`

### 3. `src/agent_ls/graph/nodes/plan.py`
- **Line 42:** Change `user_msg = last_message.content` to `user_msg = message_content_as_text(last_message.content)`
- **Line 52:** Change `json.loads(response.content)` to `json.loads(message_content_as_text(response.content))`
- Add import: `from agent_ls.graph.utils import message_content_as_text`

### 4. `src/agent_ls/graph/nodes/extract.py`
- **Line 47:** Change `json.loads(response.content)` to `json.loads(message_content_as_text(response.content))`
- Add import: `from agent_ls.graph.utils import message_content_as_text`

### 5. `src/agent_ls/graph/nodes/error_recovery.py`
- **Line 55:** Change `json.loads(response.content)` to `json.loads(message_content_as_text(response.content))`
- Add import: `from agent_ls.graph.utils import message_content_as_text`

### 6. `src/agent_ls/graph/nodes/context_gather.py`
- **Line 45:** Change `json.loads(response.content)` to `json.loads(message_content_as_text(response.content))`
- Add import: `from agent_ls.graph.utils import message_content_as_text`

### 7. `src/agent_ls/graph/nodes/search.py`
- **Line 29:** Change `response.content.strip()` to `message_content_as_text(response.content).strip()`
- Add import: `from agent_ls.graph.utils import message_content_as_text`

### 8. `tests/unit/test_message_content_utils.py` (NEW FILE)
- Create comprehensive unit tests for the helper function
- Test both `str` and `list` input shapes
- Test edge cases (empty list, mixed content, dict with text field)
- Test that existing node behavior is preserved

## Implementation Approach (TDD Sequence)

### Step 1: Write the utility function tests
1. Create `tests/unit/test_message_content_utils.py`
2. Write tests covering:
   - `str` input returns unchanged
   - `list[str]` input joins with newlines
   - `list[dict]` with "text" field extracts text
   - Mixed `list[str | dict]` handles both
   - Empty string and empty list edge cases
3. Run tests - they should fail (module doesn't exist yet)

### Step 2: Implement the utility function
1. Create `src/agent_ls/graph/utils.py`
2. Implement `message_content_as_text()` with proper type hints
3. Run tests - they should pass
4. Run mypy on utils.py - should be clean

### Step 3: Update graph nodes (one file at a time)
For each of the 6 affected files:
1. Add the import statement
2. Update all call sites to use the helper
3. Run mypy on that file - errors should decrease
4. Run the existing test suite - should stay green

### Step 4: Verify all mypy errors resolved
1. Run mypy on all affected files together
2. Confirm 0 errors (was 6)
3. Run full test suite: `pytest -q`
4. Confirm 162 tests still pass

## Testing Strategy

### Unit tests for the helper function

**File:** `tests/unit/test_message_content_utils.py`

```python
"""Tests for graph utility functions."""

import pytest
from agent_ls.graph.utils import message_content_as_text


class TestMessageContentAsText:
    """Test the message_content_as_text helper for LangChain message handling."""
    
    def test_str_input_returns_unchanged(self):
        """When content is already a string, return it as-is."""
        result = message_content_as_text("hello world")
        assert result == "hello world"
    
    def test_empty_str_input(self):
        """Empty string should be preserved."""
        result = message_content_as_text("")
        assert result == ""
    
    def test_list_of_strings_joins_with_newlines(self):
        """List of strings should be joined with newlines."""
        result = message_content_as_text(["hello", "world"])
        assert result == "hello\nworld"
    
    def test_empty_list_returns_empty_string(self):
        """Empty list should return empty string."""
        result = message_content_as_text([])
        assert result == ""
    
    def test_list_with_single_string(self):
        """List with one string should return that string."""
        result = message_content_as_text(["single"])
        assert result == "single"
    
    def test_dict_with_text_field_extracts_text(self):
        """Dict with 'text' field should extract the text value."""
        content = [{"type": "text", "text": "hello from dict"}]
        result = message_content_as_text(content)
        assert result == "hello from dict"
    
    def test_mixed_str_and_dict_content(self):
        """Mixed list of strings and dicts should join all parts."""
        content = [
            "intro text",
            {"type": "text", "text": "middle text"},
            "outro text"
        ]
        result = message_content_as_text(content)
        assert result == "intro text\nmiddle text\noutro text"
    
    def test_dict_without_text_field_converts_to_str(self):
        """Dict without 'text' field should be converted to string."""
        content = [{"type": "other", "data": 123}]
        result = message_content_as_text(content)
        # Should contain some string representation
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_json_parseable_output(self):
        """For JSON parsing use cases, output should be valid."""
        import json
        content = '{"key": "value"}'
        result = message_content_as_text(content)
        # Should be able to parse without error
        parsed = json.loads(result)
        assert parsed == {"key": "value"}
    
    def test_stripable_output(self):
        """For strip() use cases, output should work correctly."""
        content = "  intent_name  "
        result = message_content_as_text(content)
        assert result.strip() == "intent_name"
    
    def test_regex_searchable_output(self):
        """For regex search use cases, output should be searchable."""
        import re
        content = "post to #engineering channel"
        result = message_content_as_text(content)
        match = re.search(r"#(\w+)", result)
        assert match is not None
        assert match.group(1) == "engineering"


class TestMessageContentIntegration:
    """Integration tests ensuring helper works with actual LangChain types."""
    
    def test_works_with_langchain_message_content(self):
        """Test with actual LangChain message types."""
        from langchain_core.messages import HumanMessage, AIMessage
        
        human = HumanMessage(content="user question")
        assert message_content_as_text(human.content) == "user question"
        
        ai = AIMessage(content="ai response")
        assert message_content_as_text(ai.content) == "ai response"
    
    def test_type_annotations_accept_union_type(self):
        """Verify the function accepts str | list[str | dict] as typed."""
        # This test validates the type signature works with mypy
        str_content: str | list[str | dict] = "text"
        list_content: str | list[str | dict] = ["text"]
        
        result1 = message_content_as_text(str_content)
        result2 = message_content_as_text(list_content)
        
        assert isinstance(result1, str)
        assert isinstance(result2, str)
```

### Regression tests

Run existing test suite to ensure no behavior changes:
- `tests/unit/test_error_recovery.py` - uses response.content in mocks
- `tests/unit/test_context_gather.py` - uses response.content in mocks
- `tests/unit/test_extract.py` - uses response.content in mocks
- `tests/unit/test_search_node.py` - uses response.content in mocks

All existing tests should pass with no modifications (they mock response.content as strings).

### Mypy verification tests

Add a test to verify mypy finds 0 errors in the affected files:

```python
class TestMypyGraphNodes:
    """Verify mypy type checking passes for all graph nodes."""
    
    def test_mypy_graph_nodes_zero_errors(self):
        """Verify mypy reports 0 errors for all affected graph files."""
        import subprocess
        
        files = [
            "src/agent_ls/graph/router.py",
            "src/agent_ls/graph/nodes/plan.py",
            "src/agent_ls/graph/nodes/extract.py",
            "src/agent_ls/graph/nodes/error_recovery.py",
            "src/agent_ls/graph/nodes/context_gather.py",
            "src/agent_ls/graph/nodes/search.py",
        ]
        
        result = subprocess.run(
            ["uv", "run", "mypy"] + files,
            capture_output=True,
            text=True,
        )
        
        assert "Found 0 errors" in result.stdout or result.returncode == 0, (
            f"Expected 0 mypy errors, but got:\n{result.stdout}\n{result.stderr}"
        )
```

## Acceptance Criteria

1. **Mypy errors eliminated:**
   - Before: 6 errors across 5 files
   - After: 0 errors
   - Verify: `mypy src/agent_ls/graph/router.py src/agent_ls/graph/nodes/*.py`

2. **All tests pass:**
   - New tests for `message_content_as_text()` pass
   - Existing 162 tests remain green
   - Verify: `pytest -q`

3. **Ruff clean:**
   - No new lint errors introduced
   - Verify: `ruff check src/ tests/`

4. **No behavior changes:**
   - All existing node tests pass without modification
   - Runtime behavior unchanged (content is always str in practice)

5. **Type safety validated:**
   - `message_content_as_text()` has proper type hints
   - Mypy can verify all call sites
   - No `# type: ignore` comments added

## Implementation Notes

### Why a helper function instead of type narrowing?

1. **Reusability:** 6 call sites need the same logic
2. **Clarity:** Single source of truth for content coercion
3. **Testability:** Can test the helper in isolation
4. **Maintainability:** Future changes only need to update one function

### Why not use `# type: ignore`?

Per the project's hardening goals (PLAN.md), we should "narrow the types properly" rather than ignoring them. Type safety is a deliverable, not something to work around.

### Runtime impact

Zero. At runtime, LLM responses in this codebase are always strings. The helper adds a single `isinstance()` check per message, which is negligible overhead.

### Future-proofing

If the project ever uses multi-modal models (e.g., Claude with image inputs/outputs), the helper will correctly handle list-of-parts content. The current implementation joins parts with newlines, which is reasonable for text extraction.

## Dependencies

- **Blocked by:** Deliverable 1.3 (mypy config + types-PyYAML) - ✅ COMPLETED (PR #4)
- **Blocks:** No other deliverables depend on this
- **Related:** Part of Phase 1 (Type & lint debt to zero)

## Estimated Effort

- Create utils module + tests: 30 minutes
- Update 6 graph nodes: 20 minutes (straightforward find/replace pattern)
- Verify mypy + tests: 10 minutes
- **Total:** ~1 hour

## Rollback Plan

If this change causes issues:
1. Revert the commit
2. Re-run tests to confirm 162 tests pass
3. Mypy errors will return (expected)

The change is low-risk because:
- No logic changes, only type handling
- All existing tests mock content as strings (will continue to work)
- Helper function is pure (no side effects)
