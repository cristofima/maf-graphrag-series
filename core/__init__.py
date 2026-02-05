"""
MAF + GraphRAG Series - Core Module
====================================

Part 1: GraphRAG Fundamentals

This module provides a clean Python API wrapper around GraphRAG 1.2.0,
using the official graphrag.api functions.

Modules:
    - config: Load GraphRagConfig from settings.yaml
    - data_loader: Load Parquet files as pandas DataFrames
    - search: Async search functions (local, global, drift, basic)
    - indexer: Build knowledge graph from documents

Usage:
    from core import load_all, local_search, build_index

    # Build knowledge graph
    results = await build_index()

    # Load data
    data = load_all()

    # Perform search
    response, context = await local_search("Who leads Project Alpha?", data)
"""

from core.config import get_config, get_root_dir
from core.data_loader import load_all, GraphData
from core.search import local_search, global_search
from core.indexer import build_index, build_index_sync

__all__ = [
    "get_config",
    "get_root_dir",
    "load_all",
    "GraphData",
    "local_search",
    "global_search",
    "build_index",
    "build_index_sync",
]

__version__ = "1.0.0"
