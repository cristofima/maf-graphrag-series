"""
Evaluation Configuration.

Configuration for Azure AI Evaluation SDK evaluators and optional
Azure AI Foundry integration. Loads settings from environment variables
with validation.
"""

import os
from dataclasses import dataclass, field


@dataclass
class EvalConfig:
    """Configuration for the evaluation module.

    Required (Azure OpenAI as LLM-judge):
        - AZURE_OPENAI_ENDPOINT: Azure OpenAI service endpoint
        - AZURE_OPENAI_API_KEY: Azure OpenAI API key
        - AZURE_OPENAI_CHAT_DEPLOYMENT: Chat model deployment name

    Optional (evaluation model override):
        - AZURE_OPENAI_EVAL_CHAT_DEPLOYMENT: Deployment used only by evaluators.
          Defaults to AZURE_OPENAI_CHAT_DEPLOYMENT.

    Optional (Azure AI Foundry for red teaming + dashboard):
        - AZURE_AI_PROJECT: Foundry project endpoint (e.g., https://account.services.ai.azure.com/api/projects/project)

    Optional (Monitoring):
        - APPLICATIONINSIGHTS_CONNECTION_STRING: App Insights connection string
        - OTEL_TRACING_ENDPOINT: Custom OTLP endpoint (default: Aspire at localhost:4317)
    """

    azure_endpoint: str
    api_key: str
    chat_deployment: str
    eval_chat_deployment: str
    azure_ai_project: str | None = None
    app_insights_connection_string: str | None = None
    otel_tracing_endpoint: str = "http://localhost:4317"
    api_version: str = "2024-08-01-preview"
    entities_parquet_path: str = field(default="output/create_final_entities.parquet")
    relationships_parquet_path: str = field(default="output/create_final_relationships.parquet")

    @classmethod
    def from_env(cls) -> "EvalConfig":
        """Create configuration from environment variables.

        Raises:
            ValueError: If required Azure OpenAI environment variables are missing.
        """
        azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        chat_deployment = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
        eval_chat_deployment = os.environ.get("AZURE_OPENAI_EVAL_CHAT_DEPLOYMENT", chat_deployment)

        if not azure_endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is required for evaluation (LLM-as-judge)")
        if not api_key:
            raise ValueError("AZURE_OPENAI_API_KEY is required for evaluation (LLM-as-judge)")

        return cls(
            azure_endpoint=azure_endpoint,
            api_key=api_key,
            chat_deployment=chat_deployment,
            eval_chat_deployment=eval_chat_deployment,
            azure_ai_project=os.environ.get("AZURE_AI_PROJECT"),
            app_insights_connection_string=os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"),
            otel_tracing_endpoint=os.environ.get("OTEL_TRACING_ENDPOINT", "http://localhost:4317"),
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
            entities_parquet_path=os.environ.get("ENTITIES_PARQUET_PATH", "output/create_final_entities.parquet"),
            relationships_parquet_path=os.environ.get(
                "RELATIONSHIPS_PARQUET_PATH", "output/create_final_relationships.parquet"
            ),
        )

    @property
    def model_config(self) -> dict[str, str]:
        """Return model_config dict for Azure AI Evaluation SDK evaluators."""
        return {
            "azure_endpoint": self.azure_endpoint,
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
