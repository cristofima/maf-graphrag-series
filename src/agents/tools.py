"""
Local Tool Functions for the Knowledge Captain.

Lightweight ``@tool``-decorated functions that run locally (no MCP round-trip).
These complement the remote GraphRAG MCP tools by handling pure formatting
and extraction tasks that don't require the knowledge graph.

Usage::

    from agents.tools import format_as_table, extract_key_entities

    agent = Agent(
        client=client,
        instructions="...",
        tools=[mcp_tool, format_as_table, extract_key_entities],
    )
"""

from __future__ import annotations

from typing import Any

from agent_framework import tool


@tool(
    name="format_as_table",
    description="Format a list of items as a Markdown table.",
    approval_mode="never_require",
)
def format_as_table(
    rows: list[dict[str, Any]],
    columns: list[str] | None = None,
) -> str:
    """Format a list of dictionaries as a Markdown table.

    Useful for presenting entity lists, search results, or comparison data
    in a structured, readable format.

    Args:
        rows: List of dictionaries, where each dict represents a row.
        columns: Optional column names to include (and their order).
            If omitted, uses the keys from the first row.

    Returns:
        A Markdown-formatted table string, or a message if no data.
    """
    if not rows:
        return "_No data to display._"

    cols = columns or list(rows[0].keys())
    if not cols:
        return "_No columns to display._"

    # Header
    header = "| " + " | ".join(cols) + " |"
    separator = "| " + " | ".join("---" for _ in cols) + " |"

    # Rows
    body_lines: list[str] = []
    for row in rows:
        values = [str(row.get(c, "")) for c in cols]
        body_lines.append("| " + " | ".join(values) + " |")

    return "\n".join([header, separator, *body_lines])


@tool(
    name="extract_key_entities",
    description="Extract named entities (people, projects, teams, technologies) from a text snippet.",
    approval_mode="never_require",
)
def extract_key_entities(text: str) -> list[str]:
    """Extract likely entity names from a text snippet using lightweight heuristics.

    Scans for capitalized multi-word phrases, common project-name patterns
    (e.g. "Project Alpha"), and technology keywords. This is a local operation
    — no LLM or MCP call is needed.

    Args:
        text: The text to scan for entities.

    Returns:
        Sorted, deduplicated list of candidate entity names.
    """
    import re

    if not text or not text.strip():
        return []

    entities: set[str] = set()

    # Named project patterns: "Project Alpha", "Operation Sunrise"
    project_pattern = re.compile(r"\b(Project|Operation|Initiative|Program|Team)\s+[A-Z][a-zA-Z]+\b")
    for match in project_pattern.finditer(text):
        entities.add(match.group(0))

    # Multi-word capitalized phrases (likely proper nouns): "Sarah Chen", "TechVenture Inc"
    proper_noun_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
    for match in proper_noun_pattern.finditer(text):
        candidate = match.group(0)
        # Skip common sentence starters / false positives
        _SKIP = {"The", "This", "That", "These", "Those", "What", "Which", "Where", "When", "How", "Who"}
        if candidate.split()[0] not in _SKIP:
            entities.add(candidate)

    return sorted(entities)
