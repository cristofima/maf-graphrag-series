"""Unit tests for mcp_server/tools/local_search.py — local_search_tool.

Mocks: get_graph_data (no disk I/O) and local_search (no Azure OpenAI calls).
All tests are fully deterministic and isolated.
"""

from unittest.mock import AsyncMock, patch

import pandas as pd

from core.data_loader import GraphData
from mcp_server.tools.types import MAX_QUERY_LENGTH


def _make_graph_data() -> GraphData:
    """Minimal GraphData for tests that reach the search call."""
    return GraphData(
        entities=pd.DataFrame(),
        relationships=pd.DataFrame(),
        communities=pd.DataFrame(),
        community_reports=pd.DataFrame(),
        text_units=pd.DataFrame(),
    )


def _make_context(
    entities: pd.DataFrame | None = None,
    relationships: pd.DataFrame | None = None,
    reports: pd.DataFrame | None = None,
    sources: pd.DataFrame | None = None,
) -> dict:
    """Build a minimal GraphRAG 3.x context dict."""
    return {
        "entities": entities if entities is not None else pd.DataFrame({"id": ["e1"]}),
        "relationships": relationships if relationships is not None else pd.DataFrame({"id": ["r1"]}),
        "reports": reports if reports is not None else pd.DataFrame({"id": ["rpt1"]}),
        "sources": sources,
    }


class TestLocalSearchToolValidation:
    async def test_empty_query_returns_tool_error(self):
        from mcp_server.tools.local_search import local_search_tool

        result = await local_search_tool("")
        assert "error" in result
        assert "empty" in result["error"].lower()

    async def test_whitespace_only_query_returns_tool_error(self):
        from mcp_server.tools.local_search import local_search_tool

        result = await local_search_tool("   ")
        assert "error" in result

    async def test_query_too_long_returns_tool_error(self):
        from mcp_server.tools.local_search import local_search_tool

        result = await local_search_tool("x" * (MAX_QUERY_LENGTH + 1))
        assert "error" in result
        assert str(MAX_QUERY_LENGTH) in result["error"]

    async def test_invalid_community_level_returns_tool_error(self):
        from mcp_server.tools.local_search import local_search_tool

        result = await local_search_tool("valid query", community_level=99)
        assert "error" in result

    async def test_negative_community_level_returns_tool_error(self):
        from mcp_server.tools.local_search import local_search_tool

        result = await local_search_tool("valid query", community_level=-1)
        assert "error" in result


class TestLocalSearchToolSuccess:
    async def test_returns_answer_from_search(self):
        from mcp_server.tools.local_search import local_search_tool

        mock_search = AsyncMock(return_value=("Dr. Harrison leads Alpha.", _make_context()))
        with (
            patch("mcp_server.tools.local_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.local_search.local_search", mock_search),
        ):
            result = await local_search_tool("Who leads Project Alpha?")

        assert result["answer"] == "Dr. Harrison leads Alpha."

    async def test_returns_local_search_type(self):
        from mcp_server.tools.local_search import local_search_tool

        mock_search = AsyncMock(return_value=("answer", _make_context()))
        with (
            patch("mcp_server.tools.local_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.local_search.local_search", mock_search),
        ):
            result = await local_search_tool("test query")

        assert result["search_type"] == "local"

    async def test_context_counts_entities_relationships_reports(self):
        from mcp_server.tools.local_search import local_search_tool

        ctx = _make_context(
            entities=pd.DataFrame({"id": ["e1", "e2"]}),
            relationships=pd.DataFrame({"id": ["r1"]}),
            reports=pd.DataFrame({"id": ["rpt1", "rpt2", "rpt3"]}),
        )
        mock_search = AsyncMock(return_value=("answer", ctx))
        with (
            patch("mcp_server.tools.local_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.local_search.local_search", mock_search),
        ):
            result = await local_search_tool("test query")

        assert result["context"]["entities_used"] == 2
        assert result["context"]["relationships_used"] == 1
        assert result["context"]["reports_used"] == 3

    async def test_empty_context_counts_are_zero(self):
        from mcp_server.tools.local_search import local_search_tool

        mock_search = AsyncMock(return_value=("answer", {}))
        with (
            patch("mcp_server.tools.local_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.local_search.local_search", mock_search),
        ):
            result = await local_search_tool("test query")

        assert result["context"]["entities_used"] == 0
        assert result["context"]["relationships_used"] == 0
        assert result["context"]["reports_used"] == 0

    async def test_sources_resolved_when_sources_df_provided(self):
        from mcp_server.tools.local_search import local_search_tool

        text_units = pd.DataFrame({"human_readable_id": [0], "document_id": ["hash-1"]})
        documents = pd.DataFrame({"id": ["hash-1"], "title": ["project_alpha.md"]})
        data = GraphData(
            entities=pd.DataFrame(),
            relationships=pd.DataFrame(),
            communities=pd.DataFrame(),
            community_reports=pd.DataFrame(),
            text_units=text_units,
            documents=documents,
        )
        sources_df = pd.DataFrame({"id": ["0"], "text": ["relevant chunk"]})
        ctx = _make_context(sources=sources_df)
        mock_search = AsyncMock(return_value=("answer", ctx))

        with (
            patch("mcp_server.tools.local_search.get_graph_data", return_value=data),
            patch("mcp_server.tools.local_search.local_search", mock_search),
        ):
            result = await local_search_tool("test query")

        assert result["context"]["documents"] == ["project_alpha.md"]
        assert len(result["sources"]) == 1

    async def test_non_dict_context_treated_as_empty(self):
        from mcp_server.tools.local_search import local_search_tool

        mock_search = AsyncMock(return_value=("answer", None))
        with (
            patch("mcp_server.tools.local_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.local_search.local_search", mock_search),
        ):
            result = await local_search_tool("test query")

        assert result["context"]["entities_used"] == 0


class TestLocalSearchToolErrorHandling:
    async def test_file_not_found_returns_knowledge_graph_error(self):
        from mcp_server.tools.local_search import local_search_tool

        with patch(
            "mcp_server.tools.local_search.get_graph_data",
            side_effect=FileNotFoundError("entities.parquet not found"),
        ):
            result = await local_search_tool("test query")

        assert "error" in result
        assert "Knowledge graph not found" in result["error"]

    async def test_search_exception_returns_tool_error(self):
        from mcp_server.tools.local_search import local_search_tool

        with (
            patch("mcp_server.tools.local_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.local_search.local_search", AsyncMock(side_effect=RuntimeError("timeout"))),
        ):
            result = await local_search_tool("test query")

        assert "error" in result
        assert "Local search failed" in result["error"]
        assert "timeout" in result["error"]
