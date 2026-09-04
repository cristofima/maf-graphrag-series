"""Unit tests for core/search.py — async wrappers around graphrag.api search functions.

The GraphRAG API calls (``graphrag.api.local_search`` etc.) are mocked so these
tests never hit Azure OpenAI — no credentials or credits required.
"""

from unittest.mock import AsyncMock, MagicMock

import pandas as pd

from maf_graphrag.core.data_loader import GraphData
from maf_graphrag.core.search import basic_search, drift_search, global_search, local_search


def _make_graph_data() -> GraphData:
    return GraphData(
        entities=pd.DataFrame({"title": ["Alpha"]}),
        relationships=pd.DataFrame({"source": ["Alpha"]}),
        communities=pd.DataFrame({"id": ["c1"]}),
        community_reports=pd.DataFrame({"id": ["r1"]}),
        text_units=pd.DataFrame({"id": ["t1"]}),
        documents=pd.DataFrame({"title": ["doc.md"]}),
        covariates=None,
    )


class TestLocalSearch:
    async def test_forwards_data_fields_and_query(self, monkeypatch):
        data = _make_graph_data()
        mock_config = MagicMock(name="GraphRagConfig")
        mock_api_search = AsyncMock(return_value=("response text", {"entities": []}))
        monkeypatch.setattr("maf_graphrag.core.search.api.local_search", mock_api_search)

        response, context = await local_search("Who leads Alpha?", data, config=mock_config)

        assert response == "response text"
        assert context == {"entities": []}
        mock_api_search.assert_awaited_once_with(
            config=mock_config,
            entities=data.entities,
            communities=data.communities,
            community_reports=data.community_reports,
            text_units=data.text_units,
            relationships=data.relationships,
            covariates=data.covariates,
            community_level=2,
            response_type="Multiple Paragraphs",
            query="Who leads Alpha?",
        )

    async def test_uses_get_config_when_config_not_given(self, monkeypatch):
        data = _make_graph_data()
        mock_config = MagicMock(name="GraphRagConfig")
        monkeypatch.setattr("maf_graphrag.core.search.get_config", lambda: mock_config)
        mock_api_search = AsyncMock(return_value=("resp", {}))
        monkeypatch.setattr("maf_graphrag.core.search.api.local_search", mock_api_search)

        await local_search("query", data)

        _, kwargs = mock_api_search.call_args
        assert kwargs["config"] is mock_config

    async def test_custom_community_level_and_response_type(self, monkeypatch):
        data = _make_graph_data()
        mock_api_search = AsyncMock(return_value=("resp", {}))
        monkeypatch.setattr("maf_graphrag.core.search.api.local_search", mock_api_search)

        await local_search("query", data, config=MagicMock(), community_level=4, response_type="Single Sentence")

        _, kwargs = mock_api_search.call_args
        assert kwargs["community_level"] == 4
        assert kwargs["response_type"] == "Single Sentence"


class TestGlobalSearch:
    async def test_forwards_data_fields_and_defaults(self, monkeypatch):
        data = _make_graph_data()
        mock_config = MagicMock(name="GraphRagConfig")
        mock_api_search = AsyncMock(return_value=("global response", {"communities": []}))
        monkeypatch.setattr("maf_graphrag.core.search.api.global_search", mock_api_search)

        response, context = await global_search("What are the themes?", data, config=mock_config)

        assert response == "global response"
        assert context == {"communities": []}
        mock_api_search.assert_awaited_once_with(
            config=mock_config,
            entities=data.entities,
            communities=data.communities,
            community_reports=data.community_reports,
            community_level=2,
            dynamic_community_selection=False,
            response_type="Multiple Paragraphs",
            query="What are the themes?",
        )

    async def test_dynamic_community_selection_forwarded(self, monkeypatch):
        data = _make_graph_data()
        mock_api_search = AsyncMock(return_value=("resp", {}))
        monkeypatch.setattr("maf_graphrag.core.search.api.global_search", mock_api_search)

        await global_search("query", data, config=MagicMock(), dynamic_community_selection=True)

        _, kwargs = mock_api_search.call_args
        assert kwargs["dynamic_community_selection"] is True

    async def test_community_level_none_is_forwarded(self, monkeypatch):
        data = _make_graph_data()
        mock_api_search = AsyncMock(return_value=("resp", {}))
        monkeypatch.setattr("maf_graphrag.core.search.api.global_search", mock_api_search)

        await global_search("query", data, config=MagicMock(), community_level=None)

        _, kwargs = mock_api_search.call_args
        assert kwargs["community_level"] is None

    async def test_uses_get_config_when_config_not_given(self, monkeypatch):
        data = _make_graph_data()
        mock_config = MagicMock(name="GraphRagConfig")
        monkeypatch.setattr("maf_graphrag.core.search.get_config", lambda: mock_config)
        mock_api_search = AsyncMock(return_value=("resp", {}))
        monkeypatch.setattr("maf_graphrag.core.search.api.global_search", mock_api_search)

        await global_search("query", data)

        _, kwargs = mock_api_search.call_args
        assert kwargs["config"] is mock_config


class TestDriftSearch:
    async def test_forwards_data_fields(self, monkeypatch):
        data = _make_graph_data()
        mock_config = MagicMock(name="GraphRagConfig")
        mock_api_search = AsyncMock(return_value=("drift response", {"path": []}))
        monkeypatch.setattr("maf_graphrag.core.search.api.drift_search", mock_api_search)

        response, context = await drift_search("complex query", data, config=mock_config)

        assert response == "drift response"
        assert context == {"path": []}
        mock_api_search.assert_awaited_once_with(
            config=mock_config,
            entities=data.entities,
            communities=data.communities,
            community_reports=data.community_reports,
            text_units=data.text_units,
            relationships=data.relationships,
            community_level=2,
            response_type="Multiple Paragraphs",
            query="complex query",
        )

    async def test_uses_get_config_when_config_not_given(self, monkeypatch):
        data = _make_graph_data()
        mock_config = MagicMock(name="GraphRagConfig")
        monkeypatch.setattr("maf_graphrag.core.search.get_config", lambda: mock_config)
        mock_api_search = AsyncMock(return_value=("resp", {}))
        monkeypatch.setattr("maf_graphrag.core.search.api.drift_search", mock_api_search)

        await drift_search("query", data)

        _, kwargs = mock_api_search.call_args
        assert kwargs["config"] is mock_config


class TestBasicSearch:
    async def test_forwards_text_units_and_query(self, monkeypatch):
        data = _make_graph_data()
        mock_config = MagicMock(name="GraphRagConfig")
        mock_api_search = AsyncMock(return_value=("basic response", {"vectors": []}))
        monkeypatch.setattr("maf_graphrag.core.search.api.basic_search", mock_api_search)

        response, context = await basic_search("simple query", data, config=mock_config)

        assert response == "basic response"
        assert context == {"vectors": []}
        mock_api_search.assert_awaited_once_with(
            config=mock_config,
            text_units=data.text_units,
            response_type="Multiple Paragraphs",
            query="simple query",
        )

    async def test_uses_get_config_when_config_not_given(self, monkeypatch):
        data = _make_graph_data()
        mock_config = MagicMock(name="GraphRagConfig")
        monkeypatch.setattr("maf_graphrag.core.search.get_config", lambda: mock_config)
        mock_api_search = AsyncMock(return_value=("resp", {}))
        monkeypatch.setattr("maf_graphrag.core.search.api.basic_search", mock_api_search)

        await basic_search("query", data)

        _, kwargs = mock_api_search.call_args
        assert kwargs["config"] is mock_config

    async def test_custom_response_type(self, monkeypatch):
        data = _make_graph_data()
        mock_api_search = AsyncMock(return_value=("resp", {}))
        monkeypatch.setattr("maf_graphrag.core.search.api.basic_search", mock_api_search)

        await basic_search("query", data, config=MagicMock(), response_type="Single Sentence")

        _, kwargs = mock_api_search.call_args
        assert kwargs["response_type"] == "Single Sentence"
