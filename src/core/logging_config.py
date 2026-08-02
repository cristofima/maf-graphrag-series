"""Shared logging configuration for CLI, DevUI, and production-like entry points."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator

DEFAULT_NOISY_LOGGERS: tuple[str, ...] = (
    "litellm",
    "httpx",
    "httpcore",
    "openai",
    "azure",
    "mcp",
    "agent_framework",
    "agent_framework._mcp",
    "uvicorn.error",
    "uvicorn.access",
    "graphrag",
    "graphrag.query",
)

_ALLOWED_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}


class LoggingConfig(BaseModel):
    """Centralized logging configuration loaded from environment variables."""

    app_log_level: str = Field(default="INFO")
    noisy_log_level: str = Field(default="WARNING")
    asyncio_log_level: str = Field(default="CRITICAL")
    workflow_step_logs: bool = Field(default=False)
    log_format: str = Field(default="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
    log_date_format: str = Field(default="%Y-%m-%d %H:%M:%S")
    log_dir: str = Field(default="logs")
    log_file_mode: str = Field(default="a")
    log_max_bytes: int = Field(default=10_485_760)
    log_backup_count: int = Field(default=5)

    @field_validator("app_log_level", "noisy_log_level", "asyncio_log_level")
    @classmethod
    def _validate_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in _ALLOWED_LOG_LEVELS:
            raise ValueError(f"Unsupported log level '{value}'. Use one of: {', '.join(sorted(_ALLOWED_LOG_LEVELS))}")
        return normalized

    @classmethod
    def from_env(
        cls,
        *,
        default_app_log_level: str = "INFO",
        default_noisy_log_level: str = "WARNING",
        default_asyncio_log_level: str = "CRITICAL",
    ) -> LoggingConfig:
        """Build logging config from environment variables with validation."""

        data = {
            "app_log_level": default_app_log_level,
            "noisy_log_level": default_noisy_log_level,
            "asyncio_log_level": default_asyncio_log_level,
            "workflow_step_logs": os.getenv("WORKFLOW_STEP_LOGS", "false"),
            "log_format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "log_date_format": "%Y-%m-%d %H:%M:%S",
            "log_dir": "logs",
            "log_file_mode": "a",
            "log_max_bytes": os.getenv("APP_LOG_MAX_BYTES", "10485760"),
            "log_backup_count": os.getenv("APP_LOG_BACKUP_COUNT", "5"),
        }
        try:
            return cls.model_validate(data)
        except ValidationError as exc:  # pragma: no cover - defensive guard
            raise ValueError(str(exc)) from exc


@lru_cache(maxsize=1)
def get_logging_config() -> LoggingConfig:
    """Return cached logging configuration for library modules."""

    return LoggingConfig.from_env()


def _parse_level(value: str | int, fallback: int) -> int:
    """Resolve a logging level from string/int input with fallback."""

    if isinstance(value, int):
        return value

    level_name = str(value).strip().upper()
    resolved = logging.getLevelName(level_name)
    if isinstance(resolved, int):
        return resolved
    return fallback


def configure_app_logging(
    *,
    config: LoggingConfig | None = None,
    app_level: str | int | None = None,
    noisy_level: str | int | None = None,
    noisy_loggers: Sequence[str] | None = None,
    asyncio_level: str | int = logging.CRITICAL,
    fmt: str | None = None,
    datefmt: str | None = None,
    file_name: str | None = None,
    file_mode: str = "a",
) -> None:
    """Configure app logging with separate noisy-library controls.

    Environment overrides:
        APP_LOG_LEVEL: level for project logs (default: INFO)
        APP_NOISY_LOG_LEVEL: level for noisy dependencies (default: WARNING)
    """

    resolved = config or get_logging_config()

    effective_app_level = _parse_level(app_level or resolved.app_log_level, logging.INFO)
    effective_noisy_level = _parse_level(noisy_level or resolved.noisy_log_level, logging.WARNING)
    effective_asyncio_level = _parse_level(asyncio_level or resolved.asyncio_log_level, logging.CRITICAL)
    effective_format = fmt or resolved.log_format
    effective_date_format = datefmt or resolved.log_date_format
    effective_file_dir = resolved.log_dir
    effective_file_name = file_name
    effective_file_mode = file_mode or resolved.log_file_mode

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if effective_file_name is None or not str(effective_file_name).strip():
        effective_file_name = f"{Path(sys.argv[0]).stem}_{datetime.now().strftime('%Y%m%d')}.log"

    log_dir_path = Path(effective_file_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir_path / Path(effective_file_name).name

    handlers.append(
        RotatingFileHandler(
            log_file_path,
            mode=effective_file_mode,
            maxBytes=resolved.log_max_bytes,
            backupCount=resolved.log_backup_count,
            encoding="utf-8",
        )
    )

    logging.basicConfig(
        level=effective_app_level,
        format=effective_format,
        datefmt=effective_date_format,
        handlers=handlers,
        force=True,
    )

    logger_names = tuple(noisy_loggers) if noisy_loggers is not None else DEFAULT_NOISY_LOGGERS
    for name in logger_names:
        logging.getLogger(name).setLevel(effective_noisy_level)

    logging.getLogger("asyncio").setLevel(effective_asyncio_level)


def workflow_step_logs_enabled(config: LoggingConfig | None = None) -> bool:
    """Return whether per-step workflow logs should be emitted."""

    resolved = config or get_logging_config()
    return resolved.workflow_step_logs
