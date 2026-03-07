"""Unit tests for core/config.py — get_root_dir and pure utility functions."""

from pathlib import Path


class TestGetRootDir:
    def test_finds_settings_yaml(self):
        from core.config import get_root_dir

        root = get_root_dir()

        assert root.is_dir()
        assert (root / "settings.yaml").exists()

    def test_returns_path_object(self):
        from core.config import get_root_dir

        root = get_root_dir()

        assert isinstance(root, Path)
