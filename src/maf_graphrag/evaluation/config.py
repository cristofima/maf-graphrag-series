"""Evaluation configuration backed by Pydantic validation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError, field_validator

try:  # pragma: no cover - optional import guard for environments without azure-identity
    from azure.identity import ClientSecretCredential, DefaultAzureCredential
except ImportError:  # pragma: no cover
    ClientSecretCredential = DefaultAzureCredential = None  # type: ignore[assignment]

try:  # pragma: no cover - TokenCredential moved to azure-core exports
    from azure.core.credentials import TokenCredential
except ImportError:  # pragma: no cover
    TokenCredential = Any  # type: ignore[assignment]

DEFAULT_EVAL_API_VERSION = "2025-04-01-preview"


class EvalConfig(BaseModel):
    """Configuration for evaluation and monitoring helpers."""

    azure_endpoint: AnyHttpUrl = Field(..., description="Azure OpenAI endpoint for evaluators")
    api_key: str = Field(..., description="Azure OpenAI API key")
    chat_deployment: str = Field(..., description="Default chat deployment name")
    eval_chat_deployment: str = Field(..., description="Evaluator-specific deployment")
    redteam_chat_deployment: str = Field(..., description="Red-team target deployment")
    azure_ai_project: AnyHttpUrl | None = Field(
        default=None,
        description="Azure AI Foundry project URL",
    )
    app_insights_connection_string: str | None = Field(
        default=None,
        description="Application Insights connection string",
    )
    otel_tracing_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP endpoint for tracing",
    )
    api_version: str = Field(default=DEFAULT_EVAL_API_VERSION, description="Evaluator API version")
    entities_parquet_path: str = Field(
        default="output/create_final_entities.parquet",
        description="Entities parquet path",
    )
    relationships_parquet_path: str = Field(
        default="output/create_final_relationships.parquet",
        description="Relationships parquet path",
    )
    azure_tenant_id: str | None = Field(
        default=None,
        description="Tenant ID for Foundry service principal authentication",
    )
    azure_client_id: str | None = Field(
        default=None,
        description="Client ID for Foundry service principal authentication",
    )
    azure_client_secret: str | None = Field(
        default=None,
        description="Client secret for Foundry service principal authentication",
        repr=False,
    )

    @field_validator("api_key", "chat_deployment", "eval_chat_deployment", "redteam_chat_deployment")
    @classmethod
    def _ensure_non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Value cannot be empty")
        return value.strip()

    @field_validator("otel_tracing_endpoint")
    @classmethod
    def _normalize_otel_endpoint(cls, value: str) -> str:
        normalized = value.strip()
        return normalized.rstrip("/") if normalized.endswith("/") else normalized

    @field_validator("entities_parquet_path", "relationships_parquet_path")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        return value.strip()

    @field_validator("azure_tenant_id", "azure_client_id", "azure_client_secret")
    @classmethod
    def _normalize_optional_str(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped if stripped else None

    @classmethod
    def from_env(cls) -> EvalConfig:
        """Create configuration from environment variables with strict validation."""

        data = {
            "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
            "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
            "chat_deployment": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o"),
            "eval_chat_deployment": os.getenv("AZURE_OPENAI_EVAL_CHAT_DEPLOYMENT"),
            "redteam_chat_deployment": os.getenv("AZURE_OPENAI_REDTEAM_CHAT_DEPLOYMENT"),
            "azure_ai_project": os.getenv("AZURE_AI_PROJECT"),
            "app_insights_connection_string": os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"),
            "otel_tracing_endpoint": os.getenv("OTEL_TRACING_ENDPOINT", "http://localhost:4317"),
            "api_version": os.getenv("AZURE_OPENAI_EVAL_API_VERSION", DEFAULT_EVAL_API_VERSION),
            "entities_parquet_path": os.getenv(
                "ENTITIES_PARQUET_PATH",
                "output/create_final_entities.parquet",
            ),
            "relationships_parquet_path": os.getenv(
                "RELATIONSHIPS_PARQUET_PATH",
                "output/create_final_relationships.parquet",
            ),
            "azure_tenant_id": os.getenv("AZURE_TENANT_ID"),
            "azure_client_id": os.getenv("AZURE_CLIENT_ID"),
            "azure_client_secret": os.getenv("AZURE_CLIENT_SECRET"),
        }

        if data["eval_chat_deployment"] is None:
            data["eval_chat_deployment"] = data["chat_deployment"]
        if data["redteam_chat_deployment"] is None:
            data["redteam_chat_deployment"] = data["chat_deployment"]

        try:
            return cls.model_validate(data)
        except ValidationError as exc:  # pragma: no cover - defensive guard
            raise ValueError(str(exc)) from exc

    @property
    def azure_model_config(self) -> dict[str, str]:
        """Return model configuration dict for Azure AI Evaluation SDK evaluators."""

        return {
            "azure_endpoint": str(self.azure_endpoint),
            "api_key": self.api_key,
            "azure_deployment": self.eval_chat_deployment,
            "api_version": self.api_version,
        }

    @property
    def has_foundry_project(self) -> bool:
        """Check if Azure AI Foundry project URL is configured (required for red teaming)."""

        return self.azure_ai_project is not None

    @property
    def has_app_insights(self) -> bool:
        """Check if Application Insights is configured for production monitoring."""

        return self.app_insights_connection_string is not None

    @property
    def has_foundry_credentials(self) -> bool:
        """Return True when Foundry service principal credentials are configured."""

        return (
            self.azure_tenant_id is not None
            and self.azure_client_id is not None
            and self.azure_client_secret is not None
        )

    @property
    def foundry_auth_mode(self) -> str:
        """Describe the authentication mode used for Foundry publication."""

        return "client_secret" if self.has_foundry_credentials else "default_credential"

    @property
    def entities_parquet_path_obj(self) -> Path:
        """Return entities parquet path as ``Path`` instance."""

        return Path(self.entities_parquet_path)

    @property
    def relationships_parquet_path_obj(self) -> Path:
        """Return relationships parquet path as ``Path`` instance."""

        return Path(self.relationships_parquet_path)

    def build_foundry_credential(self) -> TokenCredential:
        """Construct an Azure credential for Foundry interactions."""

        if ClientSecretCredential is None or DefaultAzureCredential is None:  # pragma: no cover
            raise RuntimeError("azure-identity must be installed to build Foundry credentials.")

        if self.has_foundry_credentials:
            return ClientSecretCredential(
                tenant_id=self.azure_tenant_id,
                client_id=self.azure_client_id,
                client_secret=self.azure_client_secret,
            )

        return DefaultAzureCredential(
            exclude_interactive_browser_credential=True,
            exclude_visual_studio_code_credential=True,
            exclude_shared_token_cache_credential=True,
        )

    def build_foundry_client_kwargs(self) -> dict[str, object]:
        """Return keyword arguments for ``FoundryChatClient`` construction."""

        if not self.azure_ai_project:
            raise ValueError("AZURE_AI_PROJECT must be configured to build a Foundry client")

        kwargs: dict[str, object] = {
            "project_endpoint": str(self.azure_ai_project),
            "model": self.eval_chat_deployment,
        }

        credential = self.build_foundry_credential()
        kwargs["credential"] = credential
        return kwargs
