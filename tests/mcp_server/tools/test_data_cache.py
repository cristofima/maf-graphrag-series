"""Unit tests for mcp_server/tools/_data_cache.py — lazy singleton graph data cache.

Uses setup_method to reset the global _cached_data between tests,
ensuring full isolation without side effects between test cases.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from core.data_loader import GraphData


def _make_graph_data() -> GraphData:
    return GraphData(
        entities=pd.DataFrame({"title": ["Alpha"]}),
        relationships=pd.DataFrame(),
        communities=pd.DataFrame(),
        community_reports=pd.DataFrame(),
        text_units=pd.DataFrame(),
    )


def _reset_cache() -> None:
    """Reset the module-level singleton so each test starts cold."""
    import mcp_server.tools._data_cache as cache_module

    cache_module._cached_data = None


class TestGetGraphData:
    def setup_method(self) -> None:
        _reset_cache()

    def test_loads_data_on_first_call(self):
        from mcp_server.tools._data_cache import get_graph_data

        mock_data = _make_graph_data()
        with patch("mcp_server.tools._data_cache.load_all", return_value=mock_data) as mock_load:
            result = get_graph_data()

        mock_load.assert_called_once()
        assert result is mock_data

    def test_returns_cached_data_on_subsequent_calls(self):
        from mcp_server.tools._data_cache import get_graph_data

        mock_data = _make_graph_data()
        with patch("mcp_server.tools._data_cache.load_all", return_value=mock_data) as mock_load:
            first = get_graph_data()
            second = get_graph_data()
            third = get_graph_data()

        mock_load.assert_called_once()
        assert first is second is third

    def test_returns_same_object_identity(self):
        from mcp_server.tools._data_cache import get_graph_data

        mock_data = _make_graph_data()
        with patch("mcp_server.tools._data_cache.load_all", return_value=mock_data):
            first = get_graph_data()
            second = get_graph_data()

        assert first is second

    def test_propagates_file_not_found_from_load_all(self):
        from mcp_server.tools._data_cache import get_graph_data

        with patch(
            "mcp_server.tools._data_cache.load_all",
            side_effect=FileNotFoundError("entities.parquet missing"),
        ):
            with pytest.raises(FileNotFoundError, match="entities.parquet missing"):
                get_graph_data()

    def test_cache_remains_none_after_failed_load(self):
        """A failed load must not leave stale None in cache (next call should retry)."""
        import mcp_server.tools._data_cache as cache_module
        from mcp_server.tools._data_cache import get_graph_data

        with patch(
            "mcp_server.tools._data_cache.load_all",
            side_effect=FileNotFoundError("missing"),
        ):
            with pytest.raises(FileNotFoundError):
                get_graph_data()

        assert cache_module._cached_data is None
