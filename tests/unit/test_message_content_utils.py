"""Tests for graph utility functions."""

from __future__ import annotations

import json
import re


class TestMessageContentAsText:
    """Test the message_content_as_text helper for LangChain message handling."""

    def test_str_input_returns_unchanged(self):
        """When content is already a string, return it as-is."""
        from agent_ls.graph.utils import message_content_as_text

        result = message_content_as_text("hello world")
        assert result == "hello world"

    def test_empty_str_input(self):
        """Empty string should be preserved."""
        from agent_ls.graph.utils import message_content_as_text

        result = message_content_as_text("")
        assert result == ""

    def test_list_of_strings_joins_with_newlines(self):
        """List of strings should be joined with newlines."""
        from agent_ls.graph.utils import message_content_as_text

        result = message_content_as_text(["hello", "world"])
        assert result == "hello\nworld"

    def test_empty_list_returns_empty_string(self):
        """Empty list should return empty string."""
        from agent_ls.graph.utils import message_content_as_text

        result = message_content_as_text([])
        assert result == ""

    def test_list_with_single_string(self):
        """List with one string should return that string."""
        from agent_ls.graph.utils import message_content_as_text

        result = message_content_as_text(["single"])
        assert result == "single"

    def test_dict_with_text_field_extracts_text(self):
        """Dict with 'text' field should extract the text value."""
        from agent_ls.graph.utils import message_content_as_text

        content: list[str | dict] = [{"type": "text", "text": "hello from dict"}]
        result = message_content_as_text(content)
        assert result == "hello from dict"

    def test_mixed_str_and_dict_content(self):
        """Mixed list of strings and dicts should join all parts."""
        from agent_ls.graph.utils import message_content_as_text

        content: list[str | dict] = [
            "intro text",
            {"type": "text", "text": "middle text"},
            "outro text",
        ]
        result = message_content_as_text(content)
        assert result == "intro text\nmiddle text\noutro text"

    def test_dict_without_text_field_converts_to_str(self):
        """Dict without 'text' field should be converted to string."""
        from agent_ls.graph.utils import message_content_as_text

        content: list[str | dict] = [{"type": "other", "data": 123}]
        result = message_content_as_text(content)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_json_parseable_output(self):
        """For JSON parsing use cases, output should be valid."""
        from agent_ls.graph.utils import message_content_as_text

        content = '{"key": "value"}'
        result = message_content_as_text(content)
        parsed = json.loads(result)
        assert parsed == {"key": "value"}

    def test_stripable_output(self):
        """For strip() use cases, output should work correctly."""
        from agent_ls.graph.utils import message_content_as_text

        content = "  intent_name  "
        result = message_content_as_text(content)
        assert result.strip() == "intent_name"

    def test_regex_searchable_output(self):
        """For regex search use cases, output should be searchable."""
        from agent_ls.graph.utils import message_content_as_text

        content = "post to #engineering channel"
        result = message_content_as_text(content)
        match = re.search(r"#(\w+)", result)
        assert match is not None
        assert match.group(1) == "engineering"


class TestMessageContentIntegration:
    """Integration tests ensuring helper works with actual LangChain types."""

    def test_works_with_langchain_message_content(self):
        """Test with actual LangChain message types."""
        from langchain_core.messages import AIMessage, HumanMessage

        from agent_ls.graph.utils import message_content_as_text

        human = HumanMessage(content="user question")
        assert message_content_as_text(human.content) == "user question"

        ai = AIMessage(content="ai response")
        assert message_content_as_text(ai.content) == "ai response"

    def test_type_annotations_accept_union_type(self):
        """Verify the function accepts str | list[str | dict] as typed."""
        from agent_ls.graph.utils import message_content_as_text

        str_content: str | list[str | dict] = "text"
        list_content: str | list[str | dict] = ["text"]

        result1 = message_content_as_text(str_content)
        result2 = message_content_as_text(list_content)

        assert isinstance(result1, str)
        assert isinstance(result2, str)
