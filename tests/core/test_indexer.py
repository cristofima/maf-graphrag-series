"""Unit tests for core/indexer.py — async/sync wrappers around graphrag.api.build_index.

The GraphRAG API call (``graphrag.api.build_index``) is mocked so these tests
never trigger real indexing — no Azure OpenAI credentials or credits required.
"""

from unittest.mock import AsyncMock, MagicMock

from graphrag.config.enums import IndexingMethod

from maf_graphrag.core.indexer import build_index, build_index_sync


class TestBuildIndex:
    async def test_forwards_config_and_returns_results(self, monkeypatch):
        mock_config = MagicMock(name="GraphRagConfig")
        sentinel_results = [MagicMock(name="PipelineRunResult")]
        mock_api_build = AsyncMock(return_value=sentinel_results)
        monkeypatch.setattr("maf_graphrag.core.indexer.api.build_index", mock_api_build)

        results = await build_index(config=mock_config)

        assert results is sentinel_results
        mock_api_build.assert_awaited_once_with(
            config=mock_config,
            method=IndexingMethod.Standard,
            is_update_run=False,
            callbacks=None,
            additional_context=None,
            verbose=False,
            input_documents=None,
        )

    async def test_uses_get_config_when_config_not_given(self, monkeypatch):
        mock_config = MagicMock(name="GraphRagConfig")
        monkeypatch.setattr("maf_graphrag.core.indexer.get_config", lambda: mock_config)
        mock_api_build = AsyncMock(return_value=[])
        monkeypatch.setattr("maf_graphrag.core.indexer.api.build_index", mock_api_build)

        await build_index()

        _, kwargs = mock_api_build.call_args
        assert kwargs["config"] is mock_config

    async def test_forwards_is_update_run_and_verbose(self, monkeypatch):
        mock_api_build = AsyncMock(return_value=[])
        monkeypatch.setattr("maf_graphrag.core.indexer.api.build_index", mock_api_build)

        await build_index(config=MagicMock(), is_update_run=True, verbose=True)

        _, kwargs = mock_api_build.call_args
        assert kwargs["is_update_run"] is True
        assert kwargs["verbose"] is True


class TestBuildIndexSync:
    def test_wraps_build_index_via_asyncio_run(self, monkeypatch):
        mock_config = MagicMock(name="GraphRagConfig")
        sentinel_results = [MagicMock(name="PipelineRunResult")]
        mock_api_build = AsyncMock(return_value=sentinel_results)
        monkeypatch.setattr("maf_graphrag.core.indexer.api.build_index", mock_api_build)

        results = build_index_sync(config=mock_config)

        assert results is sentinel_results
        mock_api_build.assert_awaited_once()
