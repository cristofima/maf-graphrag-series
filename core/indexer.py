"""
GraphRAG indexing functionality.

Provides async wrapper around graphrag.api.build_index for creating knowledge graphs.
"""

import asyncio
from typing import Optional

import graphrag.api as api
from graphrag.callbacks.workflow_callbacks import WorkflowCallbacks
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.index.typing import PipelineRunResult
from graphrag.logger.base import ProgressLogger

from core.config import get_config


async def build_index(
    config: Optional[GraphRagConfig] = None,
    run_id: str = "",
    is_resume_run: bool = False,
    memory_profile: bool = False,
    callbacks: Optional[list[WorkflowCallbacks]] = None,
    progress_logger: Optional[ProgressLogger] = None,
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
        run_id: Optional run identifier for tracking
        is_resume_run: Resume from previous interrupted run
        memory_profile: Enable memory profiling
        callbacks: Custom workflow callbacks
        progress_logger: Custom progress logger
        
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
    
    # Run the indexing pipeline
    # Note: api.build_index is async in GraphRAG 1.2.0
    results = await api.build_index(
        config=config,
        run_id=run_id,
        is_resume_run=is_resume_run,
        memory_profile=memory_profile,
        callbacks=callbacks,
        progress_logger=progress_logger,
    )
    
    return results


def build_index_sync(
    config: Optional[GraphRagConfig] = None,
    run_id: str = "",
    is_resume_run: bool = False,
    memory_profile: bool = False,
    callbacks: Optional[list[WorkflowCallbacks]] = None,
    progress_logger: Optional[ProgressLogger] = None,
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
        run_id=run_id,
        is_resume_run=is_resume_run,
        memory_profile=memory_profile,
        callbacks=callbacks,
        progress_logger=progress_logger,
    ))
