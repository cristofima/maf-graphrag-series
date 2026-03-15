"""
Shared type definitions and error handling for MCP tool responses.

Provides TypedDicts that document the structure of dicts returned by MCP tools,
improving type safety at the API boundary.
"""

import functools
import logging
from collections.abc import Callable, Coroutine
from typing import Any, TypedDict

from typing_extensions import NotRequired

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input validation constants (system boundary)
# ---------------------------------------------------------------------------
MAX_QUERY_LENGTH = 2000
MAX_ENTITY_NAME_LENGTH = 200
MAX_LIMIT = 100
VALID_COMMUNITY_LEVELS = range(0, 5)


class SearchContext(TypedDict):
    """Context metadata returned by search tools."""

    entities_used: NotRequired[int]
    relationships_used: NotRequired[int]
    reports_used: NotRequired[int]
    communities_analyzed: NotRequired[int]
    documents: NotRequired[list[str]]


class SearchResult(TypedDict):
    """Successful search response from local or global search tools."""

    answer: str
    context: SearchContext
    sources: NotRequired[list[dict[str, Any]]]
    search_type: str


class EntityInfo(TypedDict):
    """Single entity in an entity query response."""

    name: str
    type: str
    description: str
    community_ids: list[Any]


class EntityQueryResult(TypedDict):
    """Successful entity query response."""

    entities: list[EntityInfo]
    total_found: int
    returned: int
    available_types: list[str]
    query_type: str


class ToolError(TypedDict):
    """Error response returned by any MCP tool."""

    error: str
    details: NotRequired[str]
    query: NotRequired[str]
    entity_name: NotRequired[str | None]
    entity_type: NotRequired[str | None]


# ---------------------------------------------------------------------------
# Input validation helpers (system boundary)
# ---------------------------------------------------------------------------


def validate_query(query: str) -> ToolError | None:
    """Return a ``ToolError`` if *query* is invalid, else ``None``."""
    if not query or not query.strip():
        return ToolError(error="Query must not be empty.")
    if len(query) > MAX_QUERY_LENGTH:
        return ToolError(error=f"Query must be at most {MAX_QUERY_LENGTH} characters (got {len(query)}).")
    return None


def validate_community_level(community_level: int | None) -> ToolError | None:
    """Return a ``ToolError`` if *community_level* is out of range."""
    if community_level is not None and community_level not in VALID_COMMUNITY_LEVELS:
        return ToolError(error=f"community_level must be 0–{VALID_COMMUNITY_LEVELS.stop - 1}.")
    return None


def validate_limit(limit: int) -> ToolError | None:
    """Return a ``ToolError`` if *limit* is out of range."""
    if limit < 1 or limit > MAX_LIMIT:
        return ToolError(error=f"limit must be 1–{MAX_LIMIT}.")
    return None


def validate_entity_name(name: str | None) -> ToolError | None:
    """Return a ``ToolError`` if *name* is too long."""
    if name is not None and len(name) > MAX_ENTITY_NAME_LENGTH:
        return ToolError(error=f"entity_name must be at most {MAX_ENTITY_NAME_LENGTH} characters.")
    return None


def handle_tool_errors(
    tool_name: str,
) -> Callable[
    [Callable[..., Coroutine[Any, Any, Any]]],
    Callable[..., Coroutine[Any, Any, Any]],
]:
    """Decorator that wraps MCP tool functions with standard error handling.

    Catches ``FileNotFoundError`` (missing index) and generic exceptions,
    returning a ``ToolError`` dict so the MCP response stays well-structured.

    Args:
        tool_name: Human-readable name used in error messages (e.g. "Local search").
    """

    def decorator(
        fn: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Callable[..., Coroutine[Any, Any, Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except FileNotFoundError as e:
                logger.warning("%s: knowledge graph not found — %s", tool_name, e)
                return ToolError(
                    error="Knowledge graph not found. Run indexing first: poetry run python -m core.index",
                    details=str(e),
                )
            except Exception as e:
                logger.exception("%s failed", tool_name)
                return ToolError(error=f"{tool_name} failed: {e}")

        return wrapper

    return decorator
