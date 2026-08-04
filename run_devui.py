"""
Run Agent Framework DevUI for local agents and workflows.

This entry point launches the DevUI web interface so you can exercise the
Knowledge Captain agent and the three workflow patterns with a richer UI,
full event tracing, and approval logging.

Usage:
    uv run python run_devui.py

Environment Variables:
    DEVUI_HOST        - Host interface (default: 127.0.0.1)
    DEVUI_PORT        - Port number (default: 8080)
    DEVUI_AUTO_OPEN   - Open browser automatically (true/false, default: true)
    DEVUI_MODE        - UI mode (developer or user, default: developer)
    APP_LOG_LEVEL     - App logging level (default: INFO)
    APP_NOISY_LOG_LEVEL - Noisy dependency logging level (default: ERROR in DevUI)
    WORKFLOW_STEP_LOGS - Enable per-step workflow logs (true/false, default: false)
"""

from __future__ import annotations

# ruff: noqa: E402
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

# Load environment variables before importing local packages
load_dotenv()

# Add src/ to sys.path for package imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from agent_framework.devui import serve
except ImportError as exc:  # pragma: no cover - dependency guidance path
    console = Console()
    console.print("[red]agent-framework-devui is not installed.[/red]")
    console.print("Install it with: [bold]uv add agent-framework-devui --pre[/bold]")
    raise SystemExit(1) from exc

from agent_framework.observability import enable_instrumentation

from agents.supervisor import create_knowledge_captain
from core.logging_config import LoggingConfig, configure_app_logging
from evaluation.monitoring.otel_setup import setup_monitoring
from workflows.base import (
    create_concurrent_workflow_runner,
    create_handoff_workflow_runner,
    create_router_workflow_runner,
    create_sequential_workflow_runner,
)

console = Console()
logger = logging.getLogger(__name__)

_LOGGERS_TO_SILENCE = (
    "litellm",
    "httpx",
    "httpcore",
    "openai",
    "azure",
    "mcp",
    "agent_framework",
    "agent_framework._mcp",
    "graphrag.query",
)


def _str_to_bool(value: str) -> bool:
    """Return True unless *value* represents a falsy flag."""
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


@dataclass
class DevUIConfig:
    """Configuration for the DevUI server."""

    host: str = "127.0.0.1"
    port: int = 8080
    auto_open: bool = True
    mode: str = "developer"
    auth_enabled: bool = False
    auth_token: str | None = None

    @classmethod
    def from_env(cls) -> DevUIConfig:
        """Build configuration from environment variables."""
        port_value = os.getenv("DEVUI_PORT", "8080")
        try:
            port = int(port_value)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError("DEVUI_PORT must be an integer") from exc

        return cls(
            host=os.getenv("DEVUI_HOST", "127.0.0.1"),
            port=port,
            auto_open=_str_to_bool(os.getenv("DEVUI_AUTO_OPEN", "true")),
            mode=os.getenv("DEVUI_MODE", "developer"),
            auth_enabled=_str_to_bool(os.getenv("DEVUI_AUTH_ENABLED", "false")),
            auth_token=os.getenv("DEVUI_AUTH_TOKEN"),
        )


def _configure_logging() -> None:
    """Configure loggers for a quiet DevUI session."""
    logging_config = LoggingConfig.from_env(default_app_log_level="INFO", default_noisy_log_level="ERROR")
    configure_app_logging(
        config=logging_config,
        noisy_loggers=_LOGGERS_TO_SILENCE,
        asyncio_level=logging.CRITICAL,
    )


def _build_entities() -> list[object]:
    """Create fresh agent and workflow instances for DevUI."""
    return [
        create_knowledge_captain(),
        create_sequential_workflow_runner(),
        create_concurrent_workflow_runner(),
        create_handoff_workflow_runner(),
        create_router_workflow_runner(),
    ]


def _print_banner(config: DevUIConfig) -> None:
    """Display launch information in a Rich panel."""
    console.print(
        Panel.fit(
            f"[bold blue]Agent Framework DevUI[/bold blue]\n\n"
            "Browse your agent and workflow runs with a richer UI."
            "\n\n"
            f"Host: [bold]{config.host}:{config.port}[/bold]\n"
            f"Auto-open browser: {'yes' if config.auto_open else 'no'}\n"
            f"Mode: {config.mode}\n"
            f"Auth required: {'yes' if config.auth_enabled else 'no'}",
            title="Visual Debugging",
        )
    )
    if config.auth_enabled and config.auth_token:
        console.print(
            Panel.fit(
                "Authentication token configured via DEVUI_AUTH_TOKEN."
                "\nProvide it as an Authorization header in DevUI.",
                title="Auth Token",
                border_style="yellow",
            )
        )


def main() -> None:
    """Entry point for launching DevUI with project entities."""
    config = DevUIConfig.from_env()
    _configure_logging()
    _print_banner(config)
    logger.info(
        "Starting DevUI on %s:%s (mode=%s, auto_open=%s)",
        config.host,
        config.port,
        config.mode,
        config.auto_open,
    )

    try:
        setup_monitoring(use_aspire=False)
        enable_instrumentation(enable_sensitive_data=True)
        logger.info("OpenTelemetry instrumentation configured for DevUI")
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.warning("OpenTelemetry setup failed: %s", exc)

    entities = _build_entities()
    logger.info("Prepared %d in-memory entities for DevUI", len(entities))

    serve_kwargs = {
        "entities": entities,
        "auto_open": config.auto_open,
        "auth_enabled": config.auth_enabled,
        "host": config.host,
        "port": config.port,
        "mode": config.mode,
    }
    if config.auth_token:
        serve_kwargs["auth_token"] = config.auth_token

    try:
        serve(**serve_kwargs)
    except KeyboardInterrupt:
        console.print("\n[yellow]DevUI stopped.[/yellow]")
    except TypeError as exc:
        if "unexpected keyword" not in str(exc):
            raise
        console.print(
            "\n[yellow]DevUI backend rejected one or more optional parameters; retrying with defaults.[/yellow]"
        )
        minimal_kwargs = {
            "entities": entities,
            "auto_open": config.auto_open,
            "auth_enabled": config.auth_enabled,
            "host": config.host,
            "port": config.port,
        }
        if config.auth_token:
            minimal_kwargs["auth_token"] = config.auth_token
        try:
            serve(**minimal_kwargs)
        except KeyboardInterrupt:
            console.print("\n[yellow]DevUI stopped.[/yellow]")


if __name__ == "__main__":
    main()
