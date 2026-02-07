"""
Search functions using GraphRAG 3.0.x API.

Provides async wrappers around graphrag.api search functions.
"""

from typing import Any

import pandas as pd

import graphrag.api as api
from graphrag.config.models.graph_rag_config import GraphRagConfig

from core.config import get_config
from core.data_loader import GraphData


# Type alias for search results
SearchResult = tuple[str, dict[str, Any]]


async def local_search(
    query: str,
    data: GraphData,
    config: GraphRagConfig | None = None,
    community_level: int = 2,
    response_type: str = "Multiple Paragraphs",
) -> SearchResult:
    """
    Perform a local search query against the knowledge graph.
    
    Local search is optimized for answering specific questions about entities
    and their direct relationships. It focuses on a subset of the knowledge graph.
    
    Best for:
        - "Who works on Project Alpha?"
        - "What technologies does Sarah Chen use?"
        - "What is the relationship between David Kumar and Emily Harrison?"
    
    Args:
        query: The question to ask
        data: GraphData object containing loaded Parquet files
        config: Optional GraphRagConfig. Uses default if not specified.
        community_level: Leiden hierarchy level (higher = smaller communities)
        response_type: Format of response (e.g., "Multiple Paragraphs", "Single Sentence")
        
    Returns:
        Tuple of (response_text, context_data)
        - response_text: The generated answer
        - context_data: Dictionary with entities, relationships used
        
    Example:
        >>> data = load_all()
        >>> response, context = await local_search("Who leads Project Alpha?", data)
        >>> print(response)
    """
    if config is None:
        config = get_config()
    
    # GraphRAG 3.x: removed 'nodes', added 'communities'
    response, context = await api.local_search(
        config=config,
        entities=data.entities,
        communities=data.communities,
        community_reports=data.community_reports,
        text_units=data.text_units,
        relationships=data.relationships,
        covariates=data.covariates,
        community_level=community_level,
        response_type=response_type,
        query=query,
    )
    
    return response, context


async def global_search(
    query: str,
    data: GraphData,
    config: GraphRagConfig | None = None,
    community_level: int | None = 2,
    response_type: str = "Multiple Paragraphs",
    dynamic_community_selection: bool = False,
) -> SearchResult:
    """
    Perform a global search query against the knowledge graph.
    
    Global search is optimized for answering broad, thematic questions that
    require understanding of the entire knowledge graph and its communities.
    Uses a map-reduce approach over community reports.
    
    Best for:
        - "What are the main projects at TechVenture?"
        - "Summarize the organizational structure"
        - "What are the key technologies being used?"
        - "What are the relationships between departments?"
    
    Args:
        query: The question to ask
        data: GraphData object containing loaded Parquet files
        config: Optional GraphRagConfig. Uses default if not specified.
        community_level: Leiden hierarchy level (higher = smaller communities). None for auto.
        response_type: Format of response (e.g., "Multiple Paragraphs", "Multi-Page Report")
        dynamic_community_selection: Use dynamic community selection algorithm
        
    Returns:
        Tuple of (response_text, context_data)
        - response_text: The generated answer
        - context_data: Dictionary with communities analyzed
        
    Example:
        >>> data = load_all()
        >>> response, context = await global_search("What are the main themes?", data)
        >>> print(response)
    """
    if config is None:
        config = get_config()
    
    # GraphRAG 3.x: removed 'nodes', community_level accepts None
    response, context = await api.global_search(
        config=config,
        entities=data.entities,
        communities=data.communities,
        community_reports=data.community_reports,
        community_level=community_level,
        dynamic_community_selection=dynamic_community_selection,
        response_type=response_type,
        query=query,
    )
    
    return response, context


async def drift_search(
    query: str,
    data: GraphData,
    config: GraphRagConfig | None = None,
    community_level: int = 2,
    response_type: str = "Multiple Paragraphs",
) -> SearchResult:
    """
    Perform a DRIFT search query against the knowledge graph.
    
    DRIFT (Dynamic Reasoning and Inference with Flexible Traversal) search
    combines local and global search strategies for complex queries.
    
    Args:
        query: The question to ask
        data: GraphData object containing loaded Parquet files
        config: Optional GraphRagConfig. Uses default if not specified.
        community_level: Leiden hierarchy level
        response_type: Format of response
        
    Returns:
        Tuple of (response_text, context_data)
    """
    if config is None:
        config = get_config()
    
    # GraphRAG 3.x: removed 'nodes', added 'communities'
    response, context = await api.drift_search(
        config=config,
        entities=data.entities,
        communities=data.communities,
        community_reports=data.community_reports,
        text_units=data.text_units,
        relationships=data.relationships,
        community_level=community_level,
        response_type=response_type,
        query=query,
    )
    
    return response, context


async def basic_search(
    query: str,
    data: GraphData,
    config: GraphRagConfig | None = None,
    response_type: str = "Multiple Paragraphs",
) -> SearchResult:
    """
    Perform a basic RAG search (vector similarity only).
    
    This is a simpler search that doesn't use the knowledge graph structure,
    only the text embeddings. Useful for comparison with graph-enhanced search.
    
    Args:
        query: The question to ask
        data: GraphData object containing loaded Parquet files
        config: Optional GraphRagConfig. Uses default if not specified.
        response_type: Format of response
        
    Returns:
        Tuple of (response_text, context_data)
    """
    if config is None:
        config = get_config()
    
    # GraphRAG 3.x: added response_type parameter
    response, context = await api.basic_search(
        config=config,
        text_units=data.text_units,
        response_type=response_type,
        query=query,
    )
    
    return response, context
