"""Azure Monitor setup for MAF agent observability.

Configures Application Insights exporters so that Agent Framework spans,
metrics, and logs flow directly into Azure Monitor. MAF agents emit telemetry
automatically for LLM calls, tool invocations, and agent steps; this helper
simply wires the exporters and ensures instrumentation is enabled.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from core.observability import configure_azure_monitor_exporters

if TYPE_CHECKING:
    from evaluation.config import EvalConfig

logger = logging.getLogger(__name__)


def _read_bool_env(name: str) -> bool | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    return raw.lower() in {"1", "true", "yes", "on"}


def setup_monitoring(config: EvalConfig | None = None) -> None:
    """Configure Azure Monitor exporters for evaluation pipelines."""

    connection_string = (config.app_insights_connection_string if config else None) or os.getenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING"
    )

    if not connection_string:
        logger.info(
            "Application Insights connection string not provided; telemetry exporters were not configured",
        )
        return

    sensitive_flag = _read_bool_env("ENABLE_SENSITIVE_DATA")

    if configure_azure_monitor_exporters(connection_string, enable_sensitive_data=sensitive_flag):
        logger.info("Azure Monitor exporters configured for evaluation telemetry")
    else:
        logger.warning("Azure Monitor exporters could not be configured; telemetry will not be emitted")
