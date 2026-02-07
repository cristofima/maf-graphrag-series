"""
Configuration loader for GraphRAG.

Loads settings from settings.yaml and environment variables.
"""

import os
from pathlib import Path
from functools import lru_cache

from dotenv import load_dotenv
from graphrag.config.load_config import load_config
from graphrag.config.models.graph_rag_config import GraphRagConfig


def get_root_dir() -> Path:
    """Get the project root directory (where settings.yaml is located)."""
    # Start from this file and go up to find settings.yaml
    current = Path(__file__).parent.parent
    
    if (current / "settings.yaml").exists():
        return current
    
    # Fallback: try current working directory
    cwd = Path.cwd()
    if (cwd / "settings.yaml").exists():
        return cwd
    
    raise FileNotFoundError(
        "Could not find settings.yaml. "
        "Make sure you're running from the project root directory."
    )


@lru_cache(maxsize=1)
def get_config() -> GraphRagConfig:
    """
    Load GraphRAG configuration from settings.yaml.
    
    Returns:
        GraphRagConfig: The loaded configuration object.
        
    Raises:
        FileNotFoundError: If settings.yaml is not found.
        
    Note:
        This function is cached - subsequent calls return the same config.
        Environment variables are loaded from .env file automatically.
    """
    # Load environment variables
    load_dotenv()
    
    # Verify required environment variables
    required_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_CHAT_DEPLOYMENT",
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Please check your .env file."
        )
    
    root_dir = get_root_dir()
    
    return load_config(root_dir=root_dir)


def get_output_dir() -> Path:
    """Get the output directory where Parquet files are stored."""
    config = get_config()
    root = get_root_dir()
    
    # GraphRAG 3.x uses output_storage instead of storage
    output_base = getattr(config.output_storage, "base_dir", "output")
    return root / output_base


def validate_output_files(required: list[str] | None = None) -> bool:
    """
    Check if required output files exist.
    
    Args:
        required: List of required file names (without path).
                  Defaults to core files needed for search.
    
    Returns:
        True if all files exist, False otherwise.
        
    Raises:
        FileNotFoundError: If any required file is missing.
    """
    if required is None:
        # GraphRAG 3.x output file names (no create_final_ prefix)
        required = [
            "entities.parquet",
            "relationships.parquet",
            "communities.parquet",
            "community_reports.parquet",
            "text_units.parquet",
        ]
    
    output_dir = get_output_dir()
    missing = [f for f in required if not (output_dir / f).exists()]
    
    if missing:
        raise FileNotFoundError(
            f"Missing required output files: {', '.join(missing)}\n"
            f"Please run indexing first: poetry run python -m core.index"
        )
    
    return True
