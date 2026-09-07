"""Core utilities that wrap GraphRAG 3.x for the MAF + GraphRAG series.

The package exposes indexing helpers, data loaders, and async search
wrappers so workflows and entry points can share a single interface.
"""

from maf_graphrag.core.classification_utils import normalize_confidence_score
from maf_graphrag.core.config import get_config, get_root_dir
from maf_graphrag.core.data_loader import GraphData, load_all
from maf_graphrag.core.indexer import build_index, build_index_sync
from maf_graphrag.core.search import basic_search, drift_search, global_search, local_search

__all__ = [
    "get_config",
    "get_root_dir",
    "load_all",
    "GraphData",
    "local_search",
    "global_search",
    "drift_search",
    "basic_search",
    "build_index",
    "build_index_sync",
    "normalize_confidence_score",
]

__version__ = "2.0.0"
