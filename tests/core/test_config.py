"""Unit tests for core/config.py — get_root_dir and pure utility functions."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.config import get_config, get_output_dir, get_root_dir, validate_output_files


class TestGetRootDir:
    def test_finds_settings_yaml(self):
        root = get_root_dir()

        assert root.is_dir()
        assert (root / "settings.yaml").exists()

    def test_returns_path_object(self):
        root = get_root_dir()

        assert isinstance(root, Path)

    def test_raises_when_settings_yaml_not_found_anywhere(self, monkeypatch):
        monkeypatch.setattr(Path, "exists", lambda self: False)

        with pytest.raises(FileNotFoundError, match="settings.yaml"):
            get_root_dir()

    def test_returns_current_when_settings_yaml_found_next_to_module(self, monkeypatch, tmp_path):
        """Covers the primary lookup branch (settings.yaml alongside the module's grandparent dir)."""
        (tmp_path / "settings.yaml").touch()
        fake_file = tmp_path / "core" / "config.py"
        fake_file.parent.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("core.config.__file__", str(fake_file))

        result = get_root_dir()

        assert result == tmp_path


def _azure_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")


class TestGetConfig:
    def teardown_method(self):
        get_config.cache_clear()

    def test_raises_when_required_env_vars_missing(self, monkeypatch):
        get_config.cache_clear()
        for var in (
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_CHAT_DEPLOYMENT",
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        ):
            monkeypatch.delenv(var, raising=False)
        monkeypatch.setattr("core.config.load_dotenv", MagicMock())

        with pytest.raises(OSError, match="Invalid environment configuration"):
            get_config()

    def test_error_message_lists_missing_vars(self, monkeypatch):
        get_config.cache_clear()
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4o")
        monkeypatch.setenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
        monkeypatch.setattr("core.config.load_dotenv", MagicMock())

        with pytest.raises(OSError, match="api_key"):
            get_config()

    def test_returns_loaded_config_when_env_vars_present(self, monkeypatch):
        get_config.cache_clear()
        _azure_env(monkeypatch)
        monkeypatch.setattr("core.config.load_dotenv", MagicMock())
        sentinel_config = MagicMock(name="GraphRagConfig")
        mock_load_config = MagicMock(return_value=sentinel_config)
        monkeypatch.setattr("core.config.load_config", mock_load_config)

        result = get_config()

        assert result is sentinel_config
        mock_load_config.assert_called_once()

    def test_result_is_cached_across_calls(self, monkeypatch):
        get_config.cache_clear()
        _azure_env(monkeypatch)
        monkeypatch.setattr("core.config.load_dotenv", MagicMock())
        mock_load_config = MagicMock(return_value=MagicMock(name="GraphRagConfig"))
        monkeypatch.setattr("core.config.load_config", mock_load_config)

        first = get_config()
        second = get_config()

        assert first is second
        mock_load_config.assert_called_once()


class TestGetOutputDir:
    def test_joins_root_dir_with_configured_base_dir(self, monkeypatch, tmp_path):
        mock_config = MagicMock()
        mock_config.output_storage.base_dir = "custom_output"
        monkeypatch.setattr("core.config.get_config", lambda: mock_config)
        monkeypatch.setattr("core.config.get_root_dir", lambda: tmp_path)

        result = get_output_dir()

        assert result == tmp_path / "custom_output"

    def test_defaults_to_output_when_base_dir_attr_missing(self, monkeypatch, tmp_path):
        mock_config = MagicMock()
        mock_config.output_storage = object()  # no base_dir attribute at all
        monkeypatch.setattr("core.config.get_config", lambda: mock_config)
        monkeypatch.setattr("core.config.get_root_dir", lambda: tmp_path)

        result = get_output_dir()

        assert result == tmp_path / "output"


class TestValidateOutputFiles:
    def _touch_required_files(self, output_dir):
        output_dir.mkdir(parents=True, exist_ok=True)
        for name in (
            "entities.parquet",
            "relationships.parquet",
            "communities.parquet",
            "community_reports.parquet",
            "text_units.parquet",
        ):
            (output_dir / name).touch()

    def test_returns_true_when_all_default_files_present(self, monkeypatch, tmp_path):
        self._touch_required_files(tmp_path)
        monkeypatch.setattr("core.config.get_output_dir", lambda: tmp_path)

        assert validate_output_files() is True

    def test_raises_when_a_default_file_is_missing(self, monkeypatch, tmp_path):
        self._touch_required_files(tmp_path)
        (tmp_path / "entities.parquet").unlink()
        monkeypatch.setattr("core.config.get_output_dir", lambda: tmp_path)

        with pytest.raises(FileNotFoundError, match="entities.parquet"):
            validate_output_files()

    def test_custom_required_list_only_checks_given_files(self, monkeypatch, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        (tmp_path / "only_this.parquet").touch()
        monkeypatch.setattr("core.config.get_output_dir", lambda: tmp_path)

        assert validate_output_files(required=["only_this.parquet"]) is True

    def test_custom_required_list_raises_for_missing_file(self, monkeypatch, tmp_path):
        tmp_path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr("core.config.get_output_dir", lambda: tmp_path)

        with pytest.raises(FileNotFoundError, match="missing.parquet"):
            validate_output_files(required=["missing.parquet"])
