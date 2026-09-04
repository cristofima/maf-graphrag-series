"""Shared observability helpers for wiring Azure Monitor exporters."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def configure_azure_monitor_exporters(
    connection_string: str,
    *,
    enable_sensitive_data: bool | None = None,
    enable_live_metrics: bool = True,
) -> bool:
    """Configure Azure Monitor exporters for the current process.

    Returns True when exporters were configured successfully, False otherwise.
    """

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:  # pragma: no cover - optional dependency resolved at runtime
        logger.warning(
            "azure-monitor-opentelemetry package not installed; skipping Azure Monitor configuration",
        )
        return False

    try:
        from agent_framework.observability import create_resource, enable_instrumentation
    except ImportError:  # pragma: no cover - presence enforced by runtime env configuration
        logger.warning("agent-framework observability not available; skipping Azure Monitor configuration")
        return False

    os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "")

    try:
        configure_azure_monitor(
            connection_string=connection_string,
            resource=create_resource(),
            enable_live_metrics=enable_live_metrics,
        )
        enable_instrumentation(enable_sensitive_data=enable_sensitive_data)
    except Exception as exc:  # pragma: no cover - defensive guard for runtime misconfiguration
        logger.exception("Failed to configure Azure Monitor exporters: %s", exc)
        return False

    return True
