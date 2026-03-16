"""Unit tests for mcp_server/tools/entity_query.py — entity_query_tool.

Mocks get_graph_data with an in-memory entities DataFrame.
list_entity_types is called on real mock data (no patch needed — pure function).
"""

from unittest.mock import patch

import pandas as pd

from core.data_loader import GraphData
from mcp_server.tools.types import MAX_LIMIT


def _make_entities_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "title": ["Dr. Emily Harrison", "David Kumar", "Project Alpha", "Project Beta"],
            "type": ["person", "person", "project", "project"],
            "description": ["Chief scientist", "Engineer", "AI project", "ML project"],
            "community_ids": [[], [], [], []],
        }
    )


def _make_graph_data(entities: pd.DataFrame | None = None) -> GraphData:
    return GraphData(
        entities=entities if entities is not None else _make_entities_df(),
        relationships=pd.DataFrame(),
        communities=pd.DataFrame(),
        community_reports=pd.DataFrame(),
        text_units=pd.DataFrame(),
    )


class TestEntityQueryToolValidation:
    async def test_limit_zero_returns_tool_error(self):
        from mcp_server.tools.entity_query import entity_query_tool

        result = await entity_query_tool(limit=0)
        assert "error" in result

    async def test_limit_over_max_returns_tool_error(self):
        from mcp_server.tools.entity_query import entity_query_tool

        result = await entity_query_tool(limit=MAX_LIMIT + 1)
        assert "error" in result

    async def test_entity_name_too_long_returns_tool_error(self):
        from mcp_server.tools.entity_query import entity_query_tool

        result = await entity_query_tool(entity_name="x" * 201)
        assert "error" in result


class TestEntityQueryToolSuccess:
    async def test_no_filter_returns_all_entities_up_to_limit(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=_make_graph_data()):
            result = await entity_query_tool(limit=10)

        assert result["query_type"] == "entity_lookup"
        assert result["total_found"] == 4
        assert result["returned"] == 4

    async def test_filter_by_entity_name_case_insensitive(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=_make_graph_data()):
            result = await entity_query_tool(entity_name="emily")

        assert result["total_found"] == 1
        assert result["entities"][0]["name"] == "Dr. Emily Harrison"

    async def test_filter_by_entity_name_partial_match(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=_make_graph_data()):
            result = await entity_query_tool(entity_name="Project")

        assert result["total_found"] == 2
        names = [e["name"] for e in result["entities"]]
        assert "Project Alpha" in names
        assert "Project Beta" in names

    async def test_filter_by_entity_type(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=_make_graph_data()):
            result = await entity_query_tool(entity_type="project")

        assert result["total_found"] == 2
        for entity in result["entities"]:
            assert entity["type"] == "project"

    async def test_filter_by_entity_type_case_insensitive(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=_make_graph_data()):
            result = await entity_query_tool(entity_type="PERSON")

        assert result["total_found"] == 2

    async def test_limit_restricts_returned_entities(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=_make_graph_data()):
            result = await entity_query_tool(limit=2)

        assert result["returned"] == 2
        assert result["total_found"] == 4

    async def test_entity_not_found_returns_empty_list(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=_make_graph_data()):
            result = await entity_query_tool(entity_name="nonexistent entity xyz")

        assert result["total_found"] == 0
        assert result["entities"] == []

    async def test_entity_info_fields_present(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=_make_graph_data()):
            result = await entity_query_tool(entity_name="David Kumar")

        entity = result["entities"][0]
        assert entity["name"] == "David Kumar"
        assert entity["type"] == "person"
        assert entity["description"] == "Engineer"
        assert isinstance(entity["community_ids"], list)

    async def test_available_types_lists_all_unique_types(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=_make_graph_data()):
            result = await entity_query_tool()

        assert set(result["available_types"]) == {"person", "project"}

    async def test_empty_entities_df_returns_zero_found(self):
        from mcp_server.tools.entity_query import entity_query_tool

        empty_data = _make_graph_data(
            entities=pd.DataFrame({"title": [], "type": [], "description": [], "community_ids": []})
        )
        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=empty_data):
            result = await entity_query_tool()

        assert result["total_found"] == 0
        assert result["entities"] == []

    async def test_query_type_is_entity_lookup(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch("mcp_server.tools.entity_query.get_graph_data", return_value=_make_graph_data()):
            result = await entity_query_tool(entity_type="project")

        assert result["query_type"] == "entity_lookup"


class TestEntityQueryToolErrorHandling:
    async def test_file_not_found_returns_knowledge_graph_error(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch(
            "mcp_server.tools.entity_query.get_graph_data",
            side_effect=FileNotFoundError("entities.parquet missing"),
        ):
            result = await entity_query_tool()

        assert "error" in result
        assert "Knowledge graph not found" in result["error"]

    async def test_generic_exception_returns_tool_error(self):
        from mcp_server.tools.entity_query import entity_query_tool

        with patch(
            "mcp_server.tools.entity_query.get_graph_data",
            side_effect=RuntimeError("data corruption"),
        ):
            result = await entity_query_tool()

        assert "error" in result
        assert "Entity query failed" in result["error"]
