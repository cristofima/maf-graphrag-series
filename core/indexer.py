"""
GraphRAG indexing functionality.

Provides async wrapper around graphrag.api.build_index for creating knowledge graphs.
"""

import asyncio
from typing import Any

import pandas as pd

import graphrag.api as api
from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks
from graphrag.config.enums import IndexingMethod
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.index.typing.pipeline_run_result import PipelineRunResult

from core.config import get_config


async def build_index(
    config: GraphRagConfig | None = None,
    method: IndexingMethod | str = IndexingMethod.Standard,
    is_update_run: bool = False,
    callbacks: list[WorkflowCallbacks] | None = None,
    additional_context: dict[str, Any] | None = None,
    verbose: bool = False,
    input_documents: pd.DataFrame | None = None,
) -> list[PipelineRunResult]:
    """
    Build the knowledge graph from input documents.
    
    This function:
    1. Reads documents from input/documents/
    2. Extracts entities and relationships using LLM
    3. Builds community structure using Leiden algorithm
    4. Generates community reports
    5. Creates embeddings and vector store
    6. Saves results to output/
    
    Args:
        config: Optional GraphRagConfig. Uses settings.yaml if not specified.
        method: Indexing method - Standard, Fast, StandardUpdate, FastUpdate
        is_update_run: Whether to update an existing index
        callbacks: Custom workflow callbacks
        additional_context: Extra context passed to workflows
        verbose: Enable verbose logging
        input_documents: Optional pre-loaded documents DataFrame
        
    Returns:
        List of pipeline run results with statistics
        
    Example:
        >>> from core import build_index
        >>> results = await build_index()
        >>> for result in results:
        ...     print(f"{result.workflow}: {result.errors or 'success'}")
        
    Note:
        This is a long-running operation that:
        - Makes multiple LLM calls (entity extraction, summarization)
        - Processes all documents in input/documents/
        - Can take several minutes depending on document count
        - Requires valid Azure OpenAI credentials in .env
    """
    if config is None:
        config = get_config()
    
    # Run the indexing pipeline (GraphRAG 3.x API)
    results = await api.build_index(
        config=config,
        method=method,
        is_update_run=is_update_run,
        callbacks=callbacks,
        additional_context=additional_context,
        verbose=verbose,
        input_documents=input_documents,
    )
    
    return results


def build_index_sync(
    config: GraphRagConfig | None = None,
    method: IndexingMethod | str = IndexingMethod.Standard,
    is_update_run: bool = False,
    callbacks: list[WorkflowCallbacks] | None = None,
    additional_context: dict[str, Any] | None = None,
    verbose: bool = False,
    input_documents: pd.DataFrame | None = None,
) -> list[PipelineRunResult]:
    """
    Synchronous version of build_index.
    
    Wraps the async API call for use in non-async contexts.
    
    Args:
        Same as build_index()
        
    Returns:
        List of pipeline run results
        
    Example:
        >>> from core.indexer import build_index_sync
        >>> results = build_index_sync()
    """
    return asyncio.run(build_index(
        config=config,
        method=method,
        is_update_run=is_update_run,
        callbacks=callbacks,
        additional_context=additional_context,
        verbose=verbose,
        input_documents=input_documents,
    ))
