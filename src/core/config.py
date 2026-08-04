"""Configuration loader for GraphRAG with Pydantic-backed validation."""

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from graphrag.config.load_config import load_config
from graphrag.config.models.graph_rag_config import GraphRagConfig
from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator


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

    raise FileNotFoundError("Could not find settings.yaml. Make sure you're running from the project root directory.")


class CoreEnvConfig(BaseModel):
    """Environment-backed configuration required for GraphRAG."""

    api_key: str = Field(..., description="Azure OpenAI API key")
    endpoint: str = Field(..., description="Azure OpenAI endpoint")
    chat_deployment: str = Field(..., description="Primary chat deployment name")
    embedding_deployment: str = Field(..., description="Embedding deployment name")

    @field_validator("api_key", "endpoint", "chat_deployment", "embedding_deployment")
    @classmethod
    def _ensure_non_empty(cls, value: str, info: ValidationInfo) -> str:
        field_name = info.field_name or "field"
        if not value or not value.strip():
            raise ValueError(f"{field_name.replace('_', ' ').upper()} must be set in the environment")
        return value.strip()

    @classmethod
    def from_env(cls) -> "CoreEnvConfig":
        """Load configuration from environment variables."""

        load_dotenv()
        data = {
            "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
            "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
            "chat_deployment": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            "embedding_deployment": os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        }
        try:
            return cls.model_validate(data)
        except ValidationError as exc:  # pragma: no cover - defensive guard
            raise OSError(f"Invalid environment configuration: {exc}") from exc


@lru_cache(maxsize=1)
def get_config() -> GraphRagConfig:
    """Load GraphRAG configuration from settings.yaml after validating environment variables."""

    CoreEnvConfig.from_env()
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
            f"Please run indexing first: uv run python -m core.index"
        )

    return True
