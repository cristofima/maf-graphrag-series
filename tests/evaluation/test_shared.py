"""Unit tests for evaluation/evaluators/_shared.py — pure helper functions.

No external services, no disk I/O — fully deterministic.
"""

import pandas as pd
import pytest

from evaluation.evaluators._shared import (
    coerce_response_text,
    collect_assistant_text,
    collect_content_block_text,
    extract_text_from_messages,
    resolve_entity_name_column,
)


class TestResolveEntityNameColumn:
    def test_prefers_name_column(self):
        df = pd.DataFrame({"name": ["Alice"], "title": ["Alice Inc"]})
        assert resolve_entity_name_column(df) == "name"

    def test_falls_back_to_title_column(self):
        df = pd.DataFrame({"title": ["Alice Inc"]})
        assert resolve_entity_name_column(df) == "title"

    def test_raises_when_neither_column_present(self):
        df = pd.DataFrame({"unknown": ["x"]})
        with pytest.raises(ValueError, match="name.*title"):
            resolve_entity_name_column(df)


class TestCoerceResponseText:
    def test_string_passthrough(self):
        assert coerce_response_text("plain text") == "plain text"

    def test_list_of_messages_delegates_to_extract(self):
        messages = [{"role": "assistant", "content": "The answer"}]
        assert coerce_response_text(messages) == "The answer"

    def test_other_types_stringified(self):
        assert coerce_response_text(42) == "42"
        assert coerce_response_text(None) == "None"


class TestExtractTextFromMessages:
    def test_extracts_only_assistant_turns(self):
        messages = [
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer one"},
            {"role": "assistant", "content": "answer two"},
        ]
        assert extract_text_from_messages(messages) == "answer one\nanswer two"

    def test_ignores_non_dict_items(self):
        messages = ["not a dict", {"role": "assistant", "content": "ok"}]
        assert extract_text_from_messages(messages) == "ok"

    def test_empty_list_returns_empty_string(self):
        assert extract_text_from_messages([]) == ""

    def test_no_assistant_messages_returns_empty_string(self):
        messages = [{"role": "user", "content": "question"}]
        assert extract_text_from_messages(messages) == ""


class TestCollectAssistantText:
    def test_string_content_appended(self):
        parts: list[str] = []
        collect_assistant_text({"content": "hello"}, parts)
        assert parts == ["hello"]

    def test_list_content_delegates_to_block_collector(self):
        parts: list[str] = []
        collect_assistant_text({"content": [{"type": "text", "text": "block text"}]}, parts)
        assert parts == ["block text"]

    def test_missing_content_key_appends_nothing(self):
        parts: list[str] = []
        collect_assistant_text({}, parts)
        assert parts == []

    def test_non_string_non_list_content_appends_nothing(self):
        parts: list[str] = []
        collect_assistant_text({"content": 123}, parts)
        assert parts == []


class TestCollectContentBlockText:
    def test_collects_recognised_block_types(self):
        parts: list[str] = []
        content = [
            {"type": "text", "text": "first"},
            {"type": "output_text", "text": "second"},
            {"type": "input_text", "text": "third"},
        ]
        collect_content_block_text(content, parts)
        assert parts == ["first", "second", "third"]

    def test_type_matching_is_case_insensitive(self):
        parts: list[str] = []
        collect_content_block_text([{"type": "TEXT", "text": "shout"}], parts)
        assert parts == ["shout"]

    def test_skips_unrecognised_block_types(self):
        parts: list[str] = []
        collect_content_block_text([{"type": "tool_call", "text": "ignored"}], parts)
        assert parts == []

    def test_skips_non_dict_blocks(self):
        parts: list[str] = []
        collect_content_block_text(["not a dict"], parts)
        assert parts == []

    def test_skips_blocks_with_empty_or_missing_text(self):
        parts: list[str] = []
        collect_content_block_text([{"type": "text", "text": ""}, {"type": "text"}], parts)
        assert parts == []

    def test_skips_blocks_with_non_string_text(self):
        parts: list[str] = []
        collect_content_block_text([{"type": "text", "text": 123}], parts)
        assert parts == []
