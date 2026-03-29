"""Unit tests for evaluation/scripts/run_redteam.py flow selection helpers."""

import pytest

from evaluation.config import EvalConfig
from evaluation.scripts.run_redteam import (
    _build_cloud_model_target,
    _normalize_redteam_flow,
    _resolve_scan_target,
)


class TestNormalizeRedteamFlow:
    def test_default_flow_when_not_provided(self, monkeypatch):
        monkeypatch.delenv("REDTEAM_FLOW", raising=False)

        resolved = _normalize_redteam_flow(None)

        assert resolved == "cloud-model"

    def test_reads_flow_from_environment(self, monkeypatch):
        monkeypatch.setenv("REDTEAM_FLOW", "local-agent")

        resolved = _normalize_redteam_flow(None)

        assert resolved == "local-agent"

    def test_cli_flow_overrides_environment(self, monkeypatch):
        monkeypatch.setenv("REDTEAM_FLOW", "local-agent")

        resolved = _normalize_redteam_flow("cloud-model")

        assert resolved == "cloud-model"

    def test_raises_on_invalid_flow(self, monkeypatch):
        monkeypatch.delenv("REDTEAM_FLOW", raising=False)

        with pytest.raises(ValueError, match="Unsupported red team flow"):
            _normalize_redteam_flow("invalid-flow")


class TestResolveScanTarget:
    @staticmethod
    def _make_config() -> EvalConfig:
        return EvalConfig(
            azure_endpoint="https://example.openai.azure.com/",
            api_key="test-key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            api_version="2024-08-01-preview",
        )

    def test_build_cloud_model_target(self):
        config = self._make_config()

        target = _build_cloud_model_target(config)

        assert target == {
            "azure_endpoint": "https://example.openai.azure.com/",
            "api_key": "test-key",
            "azure_deployment": "gpt-4o",
            "api_version": "2024-08-01-preview",
        }

    def test_resolve_scan_target_cloud_model(self):
        config = self._make_config()

        target = _resolve_scan_target(config, "cloud-model")

        assert isinstance(target, dict)
        assert target["azure_deployment"] == "gpt-4o"

    def test_resolve_scan_target_local_agent(self):
        config = self._make_config()

        target = _resolve_scan_target(config, "local-agent")

        assert callable(target)
        assert target.__name__ == "_graphrag_agent_target"
