"""Unit tests for mcp_server/server.py — tool dispatch and app wiring.

All GraphRAG tool functions (local_search_tool, global_search_tool,
entity_query_tool) are mocked, so these tests exercise only the routing
and dispatch logic — no Azure OpenAI calls, no real credentials needed.
"""

from unittest.mock import AsyncMock, patch


class TestSearchKnowledgeGraphDispatch:
    async def test_local_dispatches_to_local_search_tool(self):
        from maf_graphrag.mcp_server.server import search_knowledge_graph

        expected = {"answer": "local answer", "context": {}, "search_type": "local"}
        with patch("maf_graphrag.mcp_server.server.local_search_tool", AsyncMock(return_value=expected)) as mock_local:
            result = await search_knowledge_graph("Who leads Project Alpha?", search_type="local")

        mock_local.assert_awaited_once_with(
            query="Who leads Project Alpha?", community_level=2, response_type="Multiple Paragraphs"
        )
        assert result is expected

    async def test_global_dispatches_to_global_search_tool(self):
        from maf_graphrag.mcp_server.server import search_knowledge_graph

        expected = {"answer": "global answer", "context": {}, "search_type": "global"}
        with patch(
            "maf_graphrag.mcp_server.server.global_search_tool", AsyncMock(return_value=expected)
        ) as mock_global:
            result = await search_knowledge_graph("What are the main themes?", search_type="global")

        mock_global.assert_awaited_once_with(
            query="What are the main themes?", community_level=2, response_type="Multiple Paragraphs"
        )
        assert result is expected

    async def test_search_type_is_case_insensitive(self):
        from maf_graphrag.mcp_server.server import search_knowledge_graph

        expected = {"answer": "answer", "context": {}, "search_type": "local"}
        with patch("maf_graphrag.mcp_server.server.local_search_tool", AsyncMock(return_value=expected)):
            result = await search_knowledge_graph("query", search_type="LOCAL")

        assert result is expected

    async def test_invalid_search_type_returns_tool_error(self):
        from maf_graphrag.mcp_server.server import search_knowledge_graph

        result = await search_knowledge_graph("query", search_type="hybrid")

        assert "error" in result
        assert "hybrid" in result["error"]


class TestLocalSearch:
    async def test_forwards_arguments_to_local_search_tool(self):
        from maf_graphrag.mcp_server.server import local_search

        expected = {"answer": "answer", "context": {}, "search_type": "local"}
        with patch("maf_graphrag.mcp_server.server.local_search_tool", AsyncMock(return_value=expected)) as mock_local:
            result = await local_search("query", community_level=1, response_type="Single Paragraph")

        mock_local.assert_awaited_once_with("query", 1, "Single Paragraph")
        assert result is expected


class TestGlobalSearch:
    async def test_forwards_arguments_and_enables_dynamic_community_selection(self):
        from maf_graphrag.mcp_server.server import global_search

        expected = {"answer": "answer", "context": {}, "search_type": "global"}
        with patch(
            "maf_graphrag.mcp_server.server.global_search_tool", AsyncMock(return_value=expected)
        ) as mock_global:
            result = await global_search("query", community_level=1, response_type="Single Paragraph")

        mock_global.assert_awaited_once_with("query", 1, "Single Paragraph", dynamic_community_selection=True)
        assert result is expected


class TestListEntities:
    async def test_forwards_entity_type_and_limit(self):
        from maf_graphrag.mcp_server.server import list_entities

        expected = {"entities": [], "total_found": 0, "returned": 0, "available_types": [], "query_type": "list"}
        with patch("maf_graphrag.mcp_server.server.entity_query_tool", AsyncMock(return_value=expected)) as mock_query:
            result = await list_entities(entity_type="person", limit=5)

        mock_query.assert_awaited_once_with(entity_type="person", limit=5)
        assert result is expected

    async def test_default_entity_type_is_none(self):
        from maf_graphrag.mcp_server.server import list_entities

        expected = {"entities": [], "total_found": 0, "returned": 0, "available_types": [], "query_type": "list"}
        with patch("maf_graphrag.mcp_server.server.entity_query_tool", AsyncMock(return_value=expected)) as mock_query:
            await list_entities()

        mock_query.assert_awaited_once_with(entity_type=None, limit=10)


class TestGetEntity:
    async def test_looks_up_single_entity_by_name(self):
        from maf_graphrag.mcp_server.server import get_entity

        expected = {"entities": [], "total_found": 1, "returned": 1, "available_types": [], "query_type": "lookup"}
        with patch("maf_graphrag.mcp_server.server.entity_query_tool", AsyncMock(return_value=expected)) as mock_query:
            result = await get_entity("Dr. Emily Harrison")

        mock_query.assert_awaited_once_with(entity_name="Dr. Emily Harrison", limit=1)
        assert result is expected


class TestServerWiring:
    def test_create_mcp_server_returns_configured_instance(self):
        from maf_graphrag.mcp_server.server import create_mcp_server, mcp

        assert create_mcp_server() is mcp

    def test_app_is_configured_asgi_application(self):
        from maf_graphrag.mcp_server.server import app

        assert callable(app)
