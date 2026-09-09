"""Unit tests for evaluation/config.py — EvalConfig Pydantic model."""

from types import SimpleNamespace

import pytest

import maf_graphrag.evaluation.config as config_module
from maf_graphrag.evaluation.config import EvalConfig


class TestEvalConfigFromEnv:
    @pytest.fixture(autouse=True)
    def _isolate_eval_env(self, monkeypatch):
        for key in (
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_CHAT_DEPLOYMENT",
            "AZURE_OPENAI_EVAL_CHAT_DEPLOYMENT",
            "AZURE_OPENAI_REDTEAM_CHAT_DEPLOYMENT",
            "AZURE_OPENAI_EVAL_API_VERSION",
            "AZURE_AI_PROJECT",
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
            "OTEL_TRACING_ENDPOINT",
            "ENTITIES_PARQUET_PATH",
            "RELATIONSHIPS_PARQUET_PATH",
        ):
            monkeypatch.delenv(key, raising=False)

    def test_minimal_valid_config(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key-123")
        monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")

        config = EvalConfig.from_env()

        assert str(config.azure_endpoint) == "https://test.openai.azure.com/"
        assert config.api_key == "test-key-123"
        assert config.chat_deployment == "gpt-4o"
        assert config.eval_chat_deployment == "gpt-4o"
        assert config.redteam_chat_deployment == "gpt-4o"
        assert config.api_version == "2025-04-01-preview"
        assert config.azure_ai_project is None
        assert str(config.otel_tracing_endpoint) == "http://localhost:4317"
        assert config.azure_tenant_id is None
        assert config.azure_client_id is None
        assert config.azure_client_secret is None

    def test_raises_when_endpoint_missing(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")

        with pytest.raises(ValueError, match="azure_endpoint"):
            EvalConfig.from_env()

    def test_raises_when_api_key_missing(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

        with pytest.raises(ValueError, match="api_key"):
            EvalConfig.from_env()

    def test_default_chat_deployment(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")

        config = EvalConfig.from_env()

        assert config.chat_deployment == "gpt-4o"
        assert config.eval_chat_deployment == "gpt-4o"
        assert config.redteam_chat_deployment == "gpt-4o"

    def test_eval_chat_deployment_override(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
        monkeypatch.setenv("AZURE_OPENAI_EVAL_CHAT_DEPLOYMENT", "gpt-4.1-mini")

        config = EvalConfig.from_env()

        assert config.chat_deployment == "gpt-4o"
        assert config.eval_chat_deployment == "gpt-4.1-mini"

    def test_redteam_chat_deployment_override(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
        monkeypatch.setenv("AZURE_OPENAI_REDTEAM_CHAT_DEPLOYMENT", "gpt-4o-redteam")

        config = EvalConfig.from_env()

        assert config.chat_deployment == "gpt-4o"
        assert config.redteam_chat_deployment == "gpt-4o-redteam"

    def test_optional_foundry_config(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("AZURE_AI_PROJECT", "https://account.services.ai.azure.com/api/projects/proj")

        config = EvalConfig.from_env()

        assert str(config.azure_ai_project) == "https://account.services.ai.azure.com/api/projects/proj"

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

    def test_foundry_credential_env_fields(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("AZURE_CLIENT_ID", "client")
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "secret")
        monkeypatch.setenv("AZURE_TENANT_ID", "tenant")

        config = EvalConfig.from_env()

        assert config.azure_client_id == "client"
        assert config.azure_client_secret == "secret"
        assert config.azure_tenant_id == "tenant"
        assert config.has_foundry_credentials is True

    def test_custom_parquet_paths(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("ENTITIES_PARQUET_PATH", "custom/entities.parquet")
        monkeypatch.setenv("RELATIONSHIPS_PARQUET_PATH", "custom/relationships.parquet")

        config = EvalConfig.from_env()

        assert str(config.entities_parquet_path) == "custom/entities.parquet"
        assert str(config.relationships_parquet_path) == "custom/relationships.parquet"

    def test_custom_otel_endpoint(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("OTEL_TRACING_ENDPOINT", "http://jaeger:4317")

        config = EvalConfig.from_env()

        assert str(config.otel_tracing_endpoint) == "http://jaeger:4317"

    def test_eval_api_version_override(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")
        monkeypatch.setenv("AZURE_OPENAI_EVAL_API_VERSION", "2024-06-01")

        config = EvalConfig.from_env()

        assert config.api_version == "2024-06-01"


class TestEvalConfigProperties:
    def test_model_config_dict(self):
        config = EvalConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4.1-mini",
            redteam_chat_deployment="gpt-4o-redteam",
        )

        mc = config.azure_model_config

        assert mc == {
            "azure_endpoint": "https://test.openai.azure.com/",
            "api_key": "test-key",
            "azure_deployment": "gpt-4.1-mini",
            "api_version": "2025-04-01-preview",
        }

    def test_has_foundry_project_true(self):
        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o",
            azure_ai_project="https://proj.services.ai.azure.com/api/projects/p",
        )
        assert config.has_foundry_project is True

    def test_has_foundry_project_false(self):
        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o",
        )
        assert config.has_foundry_project is False

    def test_has_app_insights_true(self):
        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o",
            app_insights_connection_string="InstrumentationKey=abc",
        )
        assert config.has_app_insights is True

    def test_has_app_insights_false(self):
        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o",
        )
        assert config.has_app_insights is False

    def test_default_parquet_paths(self):
        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o",
        )
        assert str(config.entities_parquet_path) == "output/create_final_entities.parquet"
        assert str(config.relationships_parquet_path) == "output/create_final_relationships.parquet"

    def test_build_foundry_credential_prefers_client_secret(self, monkeypatch):
        sentinel = object()

        class FakeCredential:
            def __init__(self, *, tenant_id, client_id, client_secret):
                assert tenant_id == "tenant"
                assert client_id == "client"
                assert client_secret == "secret"
                self.marker = sentinel

        class FailDefault:
            def __init__(self, **_kwargs):  # pragma: no cover - defensive
                raise AssertionError("Default credential should not be constructed")

        monkeypatch.setattr(config_module, "ClientSecretCredential", FakeCredential, raising=True)
        monkeypatch.setattr(config_module, "DefaultAzureCredential", FailDefault, raising=True)

        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o",
            azure_ai_project="https://account.services.ai.azure.com/api/projects/proj",
            azure_tenant_id="tenant",
            azure_client_id="client",
            azure_client_secret="secret",
        )

        credential = config.build_foundry_credential()

        assert getattr(credential, "marker", None) is sentinel

    def test_build_foundry_credential_uses_default_when_no_secret(self, monkeypatch):
        sentinel = object()

        monkeypatch.setattr(config_module, "ClientSecretCredential", SimpleNamespace, raising=True)

        class FakeDefault:
            def __init__(self, **kwargs):
                assert kwargs.get("exclude_interactive_browser_credential") is True
                assert kwargs.get("exclude_visual_studio_code_credential") is True
                assert kwargs.get("exclude_shared_token_cache_credential") is True
                self.marker = sentinel

        monkeypatch.setattr(config_module, "DefaultAzureCredential", FakeDefault, raising=True)

        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o",
            azure_ai_project="https://account.services.ai.azure.com/api/projects/proj",
        )

        credential = config.build_foundry_credential()

        assert getattr(credential, "marker", None) is sentinel

    def test_build_foundry_client_kwargs_includes_endpoint_and_model(self, monkeypatch):
        sentinel = object()

        config = EvalConfig(
            azure_endpoint="https://e.openai.azure.com/",
            api_key="k",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o-eval",
            redteam_chat_deployment="gpt-4o",
            azure_ai_project="https://account.services.ai.azure.com/api/projects/proj",
        )

        monkeypatch.setattr(EvalConfig, "build_foundry_credential", lambda self: sentinel, raising=False)

        kwargs = config.build_foundry_client_kwargs()

        assert kwargs["project_endpoint"] == "https://account.services.ai.azure.com/api/projects/proj"
        assert kwargs["model"] == "gpt-4o-eval"
        assert kwargs["credential"] is sentinel
        assert config.foundry_auth_mode == "default_credential"
