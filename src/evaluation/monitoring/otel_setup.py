"""
OpenTelemetry setup for MAF agent observability.

Configures OpenTelemetry providers for tracing agent interactions
using gen_ai semantic conventions. MAF agents emit spans automatically
for LLM calls, tool invocations, and agent steps.

Supports two modes:
    - Local dev: .NET Aspire Dashboard (set OTEL_EXPORTER_OTLP_ENDPOINT)
    - Production: Application Insights (set APPLICATIONINSIGHTS_CONNECTION_STRING)
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evaluation.config import EvalConfig

logger = logging.getLogger(__name__)


def setup_monitoring(config: EvalConfig | None = None, *, use_aspire: bool = True) -> None:
    """Configure OpenTelemetry for agent observability.

    MAF agents automatically emit ``gen_ai.*`` spans — LLM calls,
    tool invocations, and agent steps are traced without manual
    instrumentation.

    The ``configure_otel_providers()`` function picks up configuration
    from environment variables:
    - ``OTEL_EXPORTER_OTLP_ENDPOINT`` for Aspire Dashboard
    - ``APPLICATIONINSIGHTS_CONNECTION_STRING`` for Application Insights

    Args:
        config: Evaluation config with telemetry settings. If None,
            uses defaults (Aspire dashboard).
        use_aspire: If True, set OTEL_EXPORTER_OTLP_ENDPOINT for
            local Aspire Dashboard. If False, rely on existing env vars.
    """
    from agent_framework.observability import configure_otel_providers

    if use_aspire and not (config and config.has_app_insights):
        endpoint = config.otel_tracing_endpoint if config else "http://localhost:4317"
        os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", endpoint)
        logger.info("OpenTelemetry: Aspire Dashboard endpoint set to %s", endpoint)

    configure_otel_providers()

    if config and config.has_app_insights:
        logger.info("OpenTelemetry configured with Application Insights")
    elif use_aspire:
        logger.info("OpenTelemetry configured with Aspire Dashboard")
    else:
        logger.info("OpenTelemetry configured with default providers")
