"""Unit tests for evaluation/monitoring/otel_setup.py — OpenTelemetry configuration."""

import os
from unittest.mock import patch

from evaluation.config import EvalConfig
from evaluation.monitoring.otel_setup import setup_monitoring


class TestSetupMonitoring:
    @patch("agent_framework.observability.configure_otel_providers")
    def test_aspire_mode_default(self, mock_configure, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        setup_monitoring(use_aspire=True)
        mock_configure.assert_called_once()
        assert os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") == "http://localhost:4317"

    @patch("agent_framework.observability.configure_otel_providers")
    def test_aspire_mode_custom_endpoint(self, mock_configure, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        config = EvalConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            otel_tracing_endpoint="http://jaeger:4317",
        )
        setup_monitoring(config, use_aspire=True)
        mock_configure.assert_called_once()
        assert os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") == "http://jaeger:4317"

    @patch("agent_framework.observability.configure_otel_providers")
    def test_app_insights_mode(self, mock_configure):
        config = EvalConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            app_insights_connection_string="InstrumentationKey=abc",
        )
        setup_monitoring(config, use_aspire=False)
        mock_configure.assert_called_once()

    @patch("agent_framework.observability.configure_otel_providers")
    def test_default_providers_fallback(self, mock_configure):
        config = EvalConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
        )
        setup_monitoring(config, use_aspire=False)
        mock_configure.assert_called_once()

    @patch("agent_framework.observability.configure_otel_providers")
    def test_none_config_uses_aspire_default(self, mock_configure, monkeypatch):
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        setup_monitoring(config=None, use_aspire=True)
        mock_configure.assert_called_once()
        assert os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") == "http://localhost:4317"

    @patch("agent_framework.observability.configure_otel_providers")
    def test_app_insights_skips_aspire_env(self, mock_configure, monkeypatch):
        """When App Insights is configured, don't set OTEL endpoint for Aspire."""
        monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
        config = EvalConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            app_insights_connection_string="InstrumentationKey=abc",
        )
        setup_monitoring(config, use_aspire=True)
        mock_configure.assert_called_once()
        # Should NOT set Aspire endpoint when App Insights is configured
        assert os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT") is None
