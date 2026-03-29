"""Unit tests for evaluation/config.py — EvalConfig dataclass."""

import pytest

from evaluation.config import EvalConfig


class TestEvalConfigFromEnv:
    def test_minimal_valid_config(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123")
        monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
        monkeypatch.delenv("AZURE_AI_PROJECT", raising=False)
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("OTEL_TRACING_ENDPOINT", raising=False)

        config = EvalConfig.from_env()

        assert config.azure_endpoint == "https://test.openai.azure.com/"
        assert config.api_key == "test-key-123"
        assert config.chat_deployment == "gpt-4o"
        assert config.eval_chat_deployment == "gpt-4o"
        assert config.azure_ai_project is None
        assert config.otel_tracing_endpoint == "http://localhost:4317"

    def test_raises_when_endpoint_missing(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")

        with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
            EvalConfig.from_env()

    def test_raises_when_api_key_missing(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="AZURE_OPENAI_API_KEY"):
            EvalConfig.from_env()

    def test_default_chat_deployment(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.delenv("AZURE_OPENAI_CHAT_DEPLOYMENT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_EVAL_CHAT_DEPLOYMENT", raising=False)

        config = EvalConfig.from_env()

        assert config.chat_deployment == "gpt-4o"
        assert config.eval_chat_deployment == "gpt-4o"

    def test_eval_chat_deployment_override(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
        monkeypatch.setenv("AZURE_OPENAI_EVAL_CHAT_DEPLOYMENT", "gpt-4.1-mini")

        config = EvalConfig.from_env()

        assert config.chat_deployment == "gpt-4o"
        assert config.eval_chat_deployment == "gpt-4.1-mini"

    def test_optional_foundry_config(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("AZURE_AI_PROJECT", "https://account.services.ai.azure.com/api/projects/proj")

        config = EvalConfig.from_env()

        assert config.azure_ai_project == "https://account.services.ai.azure.com/api/projects/proj"

    def test_app_insights_config(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
            "InstrumentationKey=00000000-0000-0000-0000-000000000000;IngestionEndpoint=https://westus-0.in.applicationinsights.azure.com/",
        )

        config = EvalConfig.from_env()

        assert config.app_insights_connection_string is not None
        assert "InstrumentationKey" in config.app_insights_connection_string

    def test_custom_parquet_paths(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("ENTITIES_PARQUET_PATH", "custom/entities.parquet")
        monkeypatch.setenv("RELATIONSHIPS_PARQUET_PATH", "custom/relationships.parquet")

        config = EvalConfig.from_env()

        assert config.entities_parquet_path == "custom/entities.parquet"
        assert config.relationships_parquet_path == "custom/relationships.parquet"

    def test_custom_otel_endpoint(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("OTEL_TRACING_ENDPOINT", "http://jaeger:4317")

        config = EvalConfig.from_env()

        assert config.otel_tracing_endpoint == "http://jaeger:4317"


class TestEvalConfigProperties:
    def test_model_config_dict(self):
        config = EvalConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4.1-mini",
        )

        mc = config.model_config

        assert mc == {
            "azure_endpoint": "https://test.openai.azure.com/",
            "api_key": "test-key",
            "azure_deployment": "gpt-4.1-mini",
            "api_version": "2024-08-01-preview",
        }

    def test_has_foundry_project_true(self):
        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            azure_ai_project="https://proj.services.ai.azure.com/api/projects/p",
        )
        assert config.has_foundry_project is True

    def test_has_foundry_project_false(self):
        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
        )
        assert config.has_foundry_project is False

    def test_has_app_insights_true(self):
        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            app_insights_connection_string="InstrumentationKey=abc",
        )
        assert config.has_app_insights is True

    def test_has_app_insights_false(self):
        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
        )
        assert config.has_app_insights is False

    def test_default_parquet_paths(self):
        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
        )
        assert config.entities_parquet_path == "output/create_final_entities.parquet"
        assert config.relationships_parquet_path == "output/create_final_relationships.parquet"
