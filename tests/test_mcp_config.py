"""Unit tests for mcp_server/config.py — MCPConfig dataclass."""

import pytest
from pathlib import Path

from mcp_server.config import MCPConfig


class TestMCPConfig:
    def test_defaults(self):
        config = MCPConfig()

        assert config.host == "127.0.0.1"
        assert config.port == 8011
        assert config.server_name == "graphrag-mcp"
        assert config.server_version == "1.0.0"
        assert config.default_community_level == 2
        assert config.default_response_type == "Multiple Paragraphs"

    def test_server_url(self):
        config = MCPConfig(host="0.0.0.0", port=9000)
        assert config.server_url == "http://0.0.0.0:9000"

    def test_server_url_default(self):
        config = MCPConfig()
        assert config.server_url == "http://127.0.0.1:8011"

    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("MCP_HOST", raising=False)
        monkeypatch.delenv("MCP_PORT", raising=False)
        monkeypatch.delenv("GRAPHRAG_ROOT", raising=False)

        config = MCPConfig.from_env()

        assert config.host == "127.0.0.1"
        assert config.port == 8011
        assert config.graphrag_root == Path(".")
        assert config.output_dir == Path("./output")

    def test_from_env_custom_values(self, monkeypatch):
        monkeypatch.setenv("MCP_HOST", "0.0.0.0")
        monkeypatch.setenv("MCP_PORT", "9000")
        monkeypatch.setenv("GRAPHRAG_ROOT", "/tmp/graphrag")

        config = MCPConfig.from_env()

        assert config.host == "0.0.0.0"
        assert config.port == 9000
        assert config.graphrag_root == Path("/tmp/graphrag")
        assert config.output_dir == Path("/tmp/graphrag/output")

    def test_port_is_integer(self, monkeypatch):
        monkeypatch.setenv("MCP_PORT", "8080")
        monkeypatch.delenv("MCP_HOST", raising=False)
        monkeypatch.delenv("GRAPHRAG_ROOT", raising=False)

        config = MCPConfig.from_env()

        assert isinstance(config.port, int)
        assert config.port == 8080
