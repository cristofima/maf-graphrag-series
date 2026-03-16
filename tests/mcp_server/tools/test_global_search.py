"""Unit tests for mcp_server/tools/global_search.py — global_search_tool.

Mocks: get_graph_data (no disk I/O) and global_search (no Azure OpenAI calls).
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


class TestGlobalSearchToolValidation:
    async def test_empty_query_returns_tool_error(self):
        from mcp_server.tools.global_search import global_search_tool

        result = await global_search_tool("")
        assert "error" in result
        assert "empty" in result["error"].lower()

    async def test_whitespace_only_query_returns_tool_error(self):
        from mcp_server.tools.global_search import global_search_tool

        result = await global_search_tool("   ")
        assert "error" in result

    async def test_query_too_long_returns_tool_error(self):
        from mcp_server.tools.global_search import global_search_tool

        result = await global_search_tool("x" * (MAX_QUERY_LENGTH + 1))
        assert "error" in result
        assert str(MAX_QUERY_LENGTH) in result["error"]

    async def test_invalid_community_level_returns_tool_error(self):
        from mcp_server.tools.global_search import global_search_tool

        result = await global_search_tool("valid query", community_level=10)
        assert "error" in result

    async def test_negative_community_level_returns_tool_error(self):
        from mcp_server.tools.global_search import global_search_tool

        result = await global_search_tool("valid query", community_level=-1)
        assert "error" in result


class TestGlobalSearchToolSuccess:
    async def test_returns_answer_from_search(self):
        from mcp_server.tools.global_search import global_search_tool

        context = {"reports": pd.DataFrame({"id": ["r1"]})}
        mock_search = AsyncMock(return_value=("There are 3 main projects.", context))
        with (
            patch("mcp_server.tools.global_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.global_search.global_search", mock_search),
        ):
            result = await global_search_tool("What are the main projects?")

        assert result["answer"] == "There are 3 main projects."

    async def test_returns_global_search_type(self):
        from mcp_server.tools.global_search import global_search_tool

        mock_search = AsyncMock(return_value=("summary", {"reports": pd.DataFrame()}))
        with (
            patch("mcp_server.tools.global_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.global_search.global_search", mock_search),
        ):
            result = await global_search_tool("summarize")

        assert result["search_type"] == "global"

    async def test_communities_analyzed_count(self):
        from mcp_server.tools.global_search import global_search_tool

        context = {"reports": pd.DataFrame({"id": ["r1", "r2", "r3"]})}
        mock_search = AsyncMock(return_value=("summary", context))
        with (
            patch("mcp_server.tools.global_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.global_search.global_search", mock_search),
        ):
            result = await global_search_tool("org structure")

        assert result["context"]["communities_analyzed"] == 3

    async def test_empty_reports_context_gives_zero_communities(self):
        from mcp_server.tools.global_search import global_search_tool

        mock_search = AsyncMock(return_value=("answer", {}))
        with (
            patch("mcp_server.tools.global_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.global_search.global_search", mock_search),
        ):
            result = await global_search_tool("test")

        assert result["context"]["communities_analyzed"] == 0

    async def test_non_dict_context_treated_as_empty(self):
        from mcp_server.tools.global_search import global_search_tool

        mock_search = AsyncMock(return_value=("answer", None))
        with (
            patch("mcp_server.tools.global_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.global_search.global_search", mock_search),
        ):
            result = await global_search_tool("test")

        assert result["context"]["communities_analyzed"] == 0

    async def test_global_search_result_has_no_sources_key(self):
        """Global search aggregates community reports — no document-level sources."""
        from mcp_server.tools.global_search import global_search_tool

        mock_search = AsyncMock(return_value=("answer", {"reports": pd.DataFrame()}))
        with (
            patch("mcp_server.tools.global_search.get_graph_data", return_value=_make_graph_data()),
            patch("mcp_server.tools.global_search.global_search", mock_search),
        ):
            result = await global_search_tool("test")

        assert "sources" not in result


class TestGlobalSearchToolErrorHandling:
    async def test_file_not_found_returns_knowledge_graph_error(self):
        from mcp_server.tools.global_search import global_search_tool

        with patch(
            "mcp_server.tools.global_search.get_graph_data",
            side_effect=FileNotFoundError("community_reports.parquet missing"),
        ):
            result = await global_search_tool("test query")

        assert "error" in result
        assert "Knowledge graph not found" in result["error"]

    async def test_search_exception_returns_tool_error(self):
        from mcp_server.tools.global_search import global_search_tool

        with (
            patch("mcp_server.tools.global_search.get_graph_data", return_value=_make_graph_data()),
            patch(
                "mcp_server.tools.global_search.global_search",
                AsyncMock(side_effect=ConnectionError("unreachable")),
            ),
        ):
            result = await global_search_tool("test query")

        assert "error" in result
        assert "Global search failed" in result["error"]
