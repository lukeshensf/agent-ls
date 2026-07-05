"""Utility functions for graph node operations."""

from __future__ import annotations


def message_content_as_text(content: str | list[str | dict]) -> str:
    """Convert LangChain message content to plain text.

    LangChain's BaseMessage.content is typed as ``str | list[str | dict]``
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
    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and "text" in item:
            # Multi-modal content block with text field
            parts.append(str(item["text"]))
        else:
            # Other dict formats - convert to string representation
            parts.append(str(item))

    return "\n".join(parts)
