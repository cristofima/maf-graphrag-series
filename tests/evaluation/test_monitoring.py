"""Unit tests for evaluation/monitoring/otel_setup.py — Azure Monitor configuration."""

from unittest.mock import patch

from evaluation.config import EvalConfig
from evaluation.monitoring.otel_setup import setup_monitoring


class TestSetupMonitoring:
    @patch("evaluation.monitoring.otel_setup.configure_azure_monitor_exporters", return_value=True)
    def test_uses_config_connection_string(self, mock_configure):
        config = EvalConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o",
            app_insights_connection_string="InstrumentationKey=abc",
        )

        setup_monitoring(config)

        mock_configure.assert_called_once_with("InstrumentationKey=abc", enable_sensitive_data=None)

    @patch("evaluation.monitoring.otel_setup.configure_azure_monitor_exporters", return_value=True)
    def test_env_connection_string_used_when_config_none(self, mock_configure, monkeypatch):
        monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=env-value")

        setup_monitoring(config=None)

        mock_configure.assert_called_once_with("InstrumentationKey=env-value", enable_sensitive_data=None)

    @patch("evaluation.monitoring.otel_setup.configure_azure_monitor_exporters", return_value=False)
    def test_logs_warning_when_configuration_fails(self, mock_configure, caplog):
        config = EvalConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o",
            app_insights_connection_string="InstrumentationKey=abc",
        )

        with caplog.at_level("WARNING"):
            setup_monitoring(config)

        assert "Azure Monitor exporters could not be configured" in caplog.text
        mock_configure.assert_called_once()

    @patch("evaluation.monitoring.otel_setup.configure_azure_monitor_exporters")
    def test_skips_when_no_connection_string(self, mock_configure, monkeypatch, caplog):
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
        config = EvalConfig(
            azure_endpoint="https://test.openai.azure.com/",
            api_key="key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o",
        )

        with caplog.at_level("INFO"):
            setup_monitoring(config)

        assert "Application Insights connection string not provided" in caplog.text
        mock_configure.assert_not_called()
