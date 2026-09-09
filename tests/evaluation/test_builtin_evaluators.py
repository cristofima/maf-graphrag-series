"""Unit tests for evaluation/evaluators/builtin.py — GraphRAG tool definitions."""

from maf_graphrag.evaluation.evaluators.builtin import GRAPHRAG_TOOL_DEFINITIONS


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
