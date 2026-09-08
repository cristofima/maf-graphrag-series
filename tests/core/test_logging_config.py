"""Tests for dual-format app logging configuration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from maf_graphrag.core.logging_config import LoggingConfig, configure_app_logging


def _read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_configure_app_logging_writes_json_file_logs(tmp_path: Path) -> None:
    config = LoggingConfig(log_dir=str(tmp_path), log_file_json=True)
    file_name = "json.log"

    configure_app_logging(config=config, file_name=file_name)
    logging.getLogger("tests.logging").info("router message")

    lines = _read_lines(tmp_path / file_name)
    assert lines
    payload = json.loads(lines[-1])
    assert payload["message"] == "router message"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "tests.logging"
    assert "timestamp" in payload


def test_configure_app_logging_can_disable_json_file_logs(tmp_path: Path) -> None:
    config = LoggingConfig(log_dir=str(tmp_path), log_file_json=False)
    file_name = "plain.log"

    configure_app_logging(config=config, file_name=file_name)
    logging.getLogger("tests.logging").info("plain message")

    lines = _read_lines(tmp_path / file_name)
    assert lines
    assert "plain message" in lines[-1]
    assert lines[-1].startswith("{") is False
