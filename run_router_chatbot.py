"""Run a local chatbot endpoint for Microsoft 365 Agents Playground.

This entry point exposes the RouterWorkflow as a single `/api/messages`
HTTP endpoint compatible with local playground activity messages.

Usage:
    uv run python run_router_chatbot.py

Environment Variables:
    ROUTER_CHATBOT_HOST              - Host interface (default: ::)
    ROUTER_CHATBOT_PORT              - Port number (default: 3978)
    ROUTER_CHATBOT_ENDPOINT          - Endpoint path (default: /api/messages)
    ROUTER_CHATBOT_TIMEOUT_SECONDS   - Router execution timeout (default: 180)
    MCP_SERVER_URL                   - Optional MCP URL override for workflows
"""

from __future__ import annotations

# ruff: noqa: E402
import logging
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# Load environment variables before importing local packages
load_dotenv()

# Add src/ to sys.path for package imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.logging_config import LoggingConfig, configure_app_logging
from workflows.router_chatbot_server import RouterChatbotConfig, create_router_chatbot_app

logger = logging.getLogger(__name__)


def main() -> None:
    """Start the local router chatbot endpoint for Agents Playground."""

    logging_config = LoggingConfig.from_env(default_app_log_level="INFO", default_noisy_log_level="WARNING")
    configure_app_logging(config=logging_config)

    config = RouterChatbotConfig.from_env()
    app = create_router_chatbot_app(config)

    logger.info(
        "Starting router chatbot endpoint at http://%s:%s%s",
        config.host,
        config.port,
        config.endpoint_path,
    )

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info",
        ws="none",
        log_config=None,
    )


if __name__ == "__main__":
    main()
