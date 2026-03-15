"""
Lazy singleton cache for GraphRAG data.

Loads the knowledge graph once on first access and reuses it for all
subsequent MCP tool calls, avoiding redundant Parquet reads on every request.
"""

import logging

from core.data_loader import GraphData, load_all

logger = logging.getLogger(__name__)

_cached_data: GraphData | None = None


def get_graph_data() -> GraphData:
    """Return cached GraphData, loading from disk on first call.

    Raises:
        FileNotFoundError: If knowledge graph files are missing.
    """
    global _cached_data  # noqa: PLW0603
    if _cached_data is None:
        logger.info("Loading knowledge graph data (first request)…")
        _cached_data = load_all()
        logger.info("Knowledge graph loaded: %s", _cached_data)
    return _cached_data
