"""
Data loader for GraphRAG output files.

Loads Parquet files into pandas DataFrames for use with graphrag.api.
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from core.config import get_output_dir, validate_output_files


@dataclass
class GraphData:
    """
    Container for all GraphRAG data needed for search operations.
    
    Attributes:
        entities: DataFrame with extracted entities
        relationships: DataFrame with entity relationships
        communities: DataFrame with community assignments
        community_reports: DataFrame with community summaries
        text_units: DataFrame with source text chunks
        documents: DataFrame with source document metadata (title, text)
        covariates: Optional DataFrame with additional entity attributes
    
    Note:
        GraphRAG 3.x removed the 'nodes' parameter from search APIs.
        Communities are now passed directly instead.
    """
    entities: pd.DataFrame
    relationships: pd.DataFrame
    communities: pd.DataFrame
    community_reports: pd.DataFrame
    text_units: pd.DataFrame
    documents: pd.DataFrame | None = None
    covariates: pd.DataFrame | None = None
    
    def __repr__(self) -> str:
        return (
            f"GraphData(\n"
            f"  entities={len(self.entities)} rows,\n"
            f"  relationships={len(self.relationships)} rows,\n"
            f"  communities={len(self.communities)} rows,\n"
            f"  community_reports={len(self.community_reports)} rows,\n"
            f"  text_units={len(self.text_units)} rows,\n"
            f"  documents={len(self.documents) if self.documents is not None else 0} rows,\n"
            f"  covariates={len(self.covariates) if self.covariates is not None else 0} rows\n"
            f")"
        )


def load_parquet(filename: str, output_dir: Path | None = None) -> pd.DataFrame:
    """
    Load a single Parquet file from the output directory.
    
    Args:
        filename: Name of the Parquet file (e.g., "entities.parquet")
        output_dir: Optional path to output directory. Uses default if not specified.
        
    Returns:
        DataFrame with the loaded data.
        
    Raises:
        FileNotFoundError: If the file doesn't exist.
    """
    if output_dir is None:
        output_dir = get_output_dir()
    
    filepath = output_dir / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    return pd.read_parquet(filepath)


def load_all(output_dir: Path | None = None, validate: bool = True) -> GraphData:
    """
    Load all GraphRAG output files needed for search operations.
    
    Args:
        output_dir: Optional path to output directory. Uses default if not specified.
        validate: Whether to validate that required files exist first.
        
    Returns:
        GraphData object containing all loaded DataFrames.
        
    Raises:
        FileNotFoundError: If any required file is missing.
        
    Example:
        >>> data = load_all()
        >>> print(f"Loaded {len(data.entities)} entities")
    """
    if output_dir is None:
        output_dir = get_output_dir()
    
    if validate:
        validate_output_files()
    
    # Load required files (GraphRAG 3.x uses simple names without prefix)
    entities = load_parquet("entities.parquet", output_dir)
    relationships = load_parquet("relationships.parquet", output_dir)
    communities = load_parquet("communities.parquet", output_dir)
    community_reports = load_parquet("community_reports.parquet", output_dir)
    text_units = load_parquet("text_units.parquet", output_dir)
    
    # Load optional files
    covariates = None
    covariates_path = output_dir / "covariates.parquet"
    if covariates_path.exists():
        covariates = load_parquet("covariates.parquet", output_dir)
    
    documents = None
    documents_path = output_dir / "documents.parquet"
    if documents_path.exists():
        documents = load_parquet("documents.parquet", output_dir)
    
    return GraphData(
        entities=entities,
        relationships=relationships,
        communities=communities,
        community_reports=community_reports,
        text_units=text_units,
        documents=documents,
        covariates=covariates,
    )


def get_entity_count(data: GraphData) -> int:
    """Get the number of entities in the graph."""
    return len(data.entities)


def get_relationship_count(data: GraphData) -> int:
    """Get the number of relationships in the graph."""
    return len(data.relationships)


def get_community_count(data: GraphData) -> int:
    """Get the number of communities in the graph."""
    return len(data.communities)


def list_entities(data: GraphData, limit: int = 20) -> list[str]:
    """
    Get a list of entity names from the graph.
    
    Args:
        data: GraphData object
        limit: Maximum number of entities to return
        
    Returns:
        List of entity names
    """
    if "name" in data.entities.columns:
        return data.entities["name"].head(limit).tolist()
    elif "title" in data.entities.columns:
        return data.entities["title"].head(limit).tolist()
    else:
        return []


def list_entity_types(data: GraphData) -> list[str]:
    """
    Get unique entity types from the graph.
    
    Args:
        data: GraphData object
        
    Returns:
        List of unique entity types
    """
    if "type" in data.entities.columns:
        return data.entities["type"].unique().tolist()
    return []
