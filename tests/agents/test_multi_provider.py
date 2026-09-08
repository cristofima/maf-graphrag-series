"""Supplementary tests for Foundry-specific AgentConfig helpers."""

import pytest

from maf_graphrag.agents.config import AgentConfig


def _seed_foundry_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "router-balanced")
    monkeypatch.setenv("AZURE_OPENAI_ROUTER_DEPLOYMENT", "router-efficient")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "key")


class TestRouterMetadata:
    def test_router_subset_can_be_empty(self, monkeypatch):
        _seed_foundry_env(monkeypatch)
        monkeypatch.delenv("AZURE_OPENAI_ROUTER_SUBSET", raising=False)

        config = AgentConfig.from_env()

        assert config.router_subset is None
