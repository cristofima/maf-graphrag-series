"""Unit tests for evaluation/evaluators/builtin.py — message conversion and tool definitions."""

from unittest.mock import MagicMock

from evaluation.evaluators.builtin import (
    GRAPHRAG_TOOL_DEFINITIONS,
    _extract_assistant_content,
    _extract_text,
    convert_to_evaluator_messages,
)


class TestGraphRAGToolDefinitions:
    def test_has_five_tools(self):
        assert len(GRAPHRAG_TOOL_DEFINITIONS) == 5

    def test_all_tools_have_required_fields(self):
        for tool in GRAPHRAG_TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert "type" in tool["parameters"]

    def test_tool_names(self):
        names = {t["name"] for t in GRAPHRAG_TOOL_DEFINITIONS}
        expected = {
            "search_knowledge_graph",
            "local_search",
            "global_search",
            "list_entities",
            "get_entity",
        }
        assert names == expected

    def test_search_knowledge_graph_has_query_required(self):
        tool = next(t for t in GRAPHRAG_TOOL_DEFINITIONS if t["name"] == "search_knowledge_graph")
        assert "query" in tool["parameters"]["properties"]
        assert "query" in tool["parameters"]["required"]


class TestExtractText:
    def test_from_text_attribute(self):
        msg = MagicMock()
        msg.text = "Hello, world"
        msg.content = None
        assert _extract_text(msg) == "Hello, world"

    def test_from_string_content(self):
        msg = MagicMock(spec=[])
        msg.content = "Plain string response"
        assert _extract_text(msg) == "Plain string response"

    def test_from_list_content_strings(self):
        msg = MagicMock(spec=[])
        msg.content = ["Part one", "Part two"]
        assert _extract_text(msg) == "Part one Part two"

    def test_from_list_content_objects(self):
        item1 = MagicMock()
        item1.text = "First"
        item2 = MagicMock()
        item2.text = "Second"
        msg = MagicMock(spec=[])
        msg.content = [item1, item2]
        assert _extract_text(msg) == "First Second"

    def test_empty_message(self):
        msg = MagicMock(spec=[])
        assert _extract_text(msg) == ""

    def test_none_text_falls_back_to_content(self):
        msg = MagicMock()
        msg.text = None
        msg.content = "Fallback content"
        assert _extract_text(msg) == "Fallback content"


class TestExtractAssistantContent:
    def test_string_content(self):
        msg = MagicMock()
        msg.content = "Simple text"
        msg.items = None
        result = _extract_assistant_content(msg)
        assert result == [{"type": "text", "text": "Simple text"}]

    def test_function_call_conversion(self):
        call_item = MagicMock()
        call_item.type = "function_call"
        call_item.call_id = "call-123"
        call_item.name = "local_search"
        call_item.arguments = {"query": "test"}

        msg = MagicMock()
        msg.content = [call_item]
        msg.items = None

        result = _extract_assistant_content(msg)

        assert len(result) == 1
        assert result[0]["type"] == "tool_call"
        tc = result[0]["tool_call"]
        assert tc["id"] == "call-123"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "local_search"
        assert tc["function"]["arguments"] == {"query": "test"}

    def test_text_item(self):
        text_item = MagicMock()
        text_item.type = "text"
        text_item.text = "Some response"
        # Ensure call_id is not present
        del text_item.call_id

        msg = MagicMock()
        msg.content = [text_item]
        msg.items = None

        result = _extract_assistant_content(msg)

        assert len(result) == 1
        assert result[0] == {"type": "text", "text": "Some response"}

    def test_empty_content_with_text_fallback(self):
        msg = MagicMock()
        msg.text = "Fallback"
        msg.content = []
        msg.items = None

        result = _extract_assistant_content(msg)

        assert result == [{"type": "text", "text": "Fallback"}]

    def test_uses_items_attribute_when_content_none(self):
        text_item = MagicMock()
        text_item.type = "text"
        text_item.text = "From items"
        del text_item.call_id

        msg = MagicMock()
        msg.content = None
        msg.items = [text_item]

        result = _extract_assistant_content(msg)

        assert result == [{"type": "text", "text": "From items"}]


class TestConvertToEvaluatorMessages:
    def test_user_message(self):
        msg = MagicMock()
        msg.role = "user"
        msg.text = "What is the CEO's name?"
        msg.content = None

        result = convert_to_evaluator_messages([msg])

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "What is the CEO's name?"

    def test_tool_message(self):
        msg = MagicMock()
        msg.role = "tool"
        msg.text = "Sarah Chen is the CEO"
        msg.tool_call_id = "call-456"
        msg.content = None

        result = convert_to_evaluator_messages([msg])

        assert len(result) == 1
        assert result[0]["role"] == "tool"
        assert result[0]["tool_call_id"] == "call-456"
        assert result[0]["content"] == [{"type": "tool_result", "tool_result": "Sarah Chen is the CEO"}]

    def test_skips_messages_without_role(self):
        msg = MagicMock(spec=[])  # No role attribute
        result = convert_to_evaluator_messages([msg])
        assert result == []

    def test_full_conversation_flow(self):
        user_msg = MagicMock()
        user_msg.role = "user"
        user_msg.text = "Who is the CEO?"
        user_msg.content = None

        call_item = MagicMock()
        call_item.type = "function_call"
        call_item.call_id = "c1"
        call_item.name = "search_knowledge_graph"
        call_item.arguments = {"query": "CEO"}

        assistant_msg = MagicMock()
        assistant_msg.role = "assistant"
        assistant_msg.content = [call_item]
        assistant_msg.items = None

        tool_msg = MagicMock()
        tool_msg.role = "tool"
        tool_msg.text = "Sarah Chen is the CEO"
        tool_msg.tool_call_id = "c1"
        tool_msg.content = None

        final_msg = MagicMock()
        final_msg.role = "assistant"
        final_msg.text = "The CEO is Sarah Chen."
        final_msg.content = []
        final_msg.items = None

        result = convert_to_evaluator_messages([user_msg, assistant_msg, tool_msg, final_msg])

        assert len(result) == 4
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[1]["content"][0]["type"] == "tool_call"
        assert result[2]["role"] == "tool"
        assert result[3]["role"] == "assistant"

    def test_handles_messagerole_prefix(self):
        """MAF role enums may stringify as 'MessageRole.user'."""
        msg = MagicMock()
        msg.role = "MessageRole.user"
        msg.text = "Query"
        msg.content = None

        result = convert_to_evaluator_messages([msg])

        assert len(result) == 1
        assert result[0]["role"] == "user"


class TestCreateQualityEvaluators:
    def test_returns_three_evaluators(self, monkeypatch):
        """Verify the factory creates the right evaluator keys (mocking SDK imports)."""
        mock_task = MagicMock()
        mock_intent = MagicMock()
        mock_tool = MagicMock()

        import evaluation.evaluators.builtin as mod

        monkeypatch.setattr(
            mod,
            "create_quality_evaluators",
            lambda mc: {"task_adherence": mock_task, "intent_resolution": mock_intent, "tool_call_accuracy": mock_tool},
        )

        result = mod.create_quality_evaluators({"azure_endpoint": "x", "api_key": "y", "azure_deployment": "z"})

        assert "task_adherence" in result
        assert "intent_resolution" in result
        assert "tool_call_accuracy" in result
        assert len(result) == 3
