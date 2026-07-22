"""Unit tests for core/index.py — run_indexing() CLI orchestration.

``build_index`` is mocked, so these tests exercise only the CLI's input
validation and result-reporting logic — no real GraphRAG indexing (which
requires Azure OpenAI credentials and costs real credits) is performed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.index import run_indexing


class TestRunIndexingValidation:
    async def test_exits_when_input_directory_is_missing(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            await run_indexing()

        assert exc_info.value.code == 1

    async def test_exits_when_input_directory_has_no_markdown_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "input" / "documents").mkdir(parents=True)

        with pytest.raises(SystemExit) as exc_info:
            await run_indexing()

        assert exc_info.value.code == 1


class TestRunIndexingHappyPath:
    async def test_calls_build_index_with_resume_flag(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        docs_dir = tmp_path / "input" / "documents"
        docs_dir.mkdir(parents=True)
        (docs_dir / "doc1.md").write_text("# Doc", encoding="utf-8")

        pipeline_result = MagicMock(workflow="create_final_documents", error=None, runtime=1.23)
        with patch("core.index.build_index", AsyncMock(return_value=[pipeline_result])) as mock_build:
            await run_indexing(resume=True)

        mock_build.assert_awaited_once_with(is_update_run=True)

    async def test_exits_when_build_index_raises(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        docs_dir = tmp_path / "input" / "documents"
        docs_dir.mkdir(parents=True)
        (docs_dir / "doc1.md").write_text("# Doc", encoding="utf-8")

        with patch("core.index.build_index", AsyncMock(side_effect=RuntimeError("boom"))):
            with pytest.raises(SystemExit) as exc_info:
                await run_indexing()

        assert exc_info.value.code == 1
