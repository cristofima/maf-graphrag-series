"""Evaluation utilities for monitoring, quality scoring, and safety checks.

The package bundles Pydantic-backed configuration, OpenTelemetry setup, scripted
evaluation entry points, and custom graph-aware evaluators used by the router-first
assistant.
"""

from maf_graphrag.evaluation.config import EvalConfig
from maf_graphrag.evaluation.monitoring.otel_setup import setup_monitoring

__all__ = ["EvalConfig", "setup_monitoring"]
