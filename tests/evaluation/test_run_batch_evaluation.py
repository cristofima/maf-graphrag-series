"""Unit tests for evaluation/scripts/run_batch_evaluation.py path handling."""

from pathlib import Path

import pytest

from evaluation.scripts.run_batch_evaluation import DATASETS_DIR, _resolve_cli_data_path


class TestResolveCliDataPath:
    def test_keeps_default_dataset_path_inside_datasets_dir(self):
        resolved = _resolve_cli_data_path("eval_data.jsonl")

        assert resolved == (DATASETS_DIR / "eval_data.jsonl").resolve()

    def test_accepts_absolute_path_within_datasets_dir(self):
        resolved = _resolve_cli_data_path(DATASETS_DIR / "eval_data.jsonl")

        assert resolved == (DATASETS_DIR / "eval_data.jsonl").resolve()

    def test_rejects_path_traversal_outside_datasets_dir(self):
        with pytest.raises(ValueError, match="must stay within"):
            _resolve_cli_data_path(Path("..") / ".." / "secrets.jsonl")

    def test_rejects_non_jsonl_files(self):
        with pytest.raises(ValueError, match=r"must point to a \.jsonl file"):
            _resolve_cli_data_path("eval_data.json")
