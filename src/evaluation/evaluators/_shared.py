"""Shared helper functions for custom evaluation modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd


def resolve_entity_name_column(entities_df: pd.DataFrame) -> str:
    """Resolve the entity text column across GraphRAG schema versions."""
    if "name" in entities_df.columns:
        return "name"
    if "title" in entities_df.columns:
        return "title"
    raise ValueError("Entities parquet must contain either 'name' or 'title' column.")


def coerce_response_text(response: object) -> str:
    """Convert evaluator response payloads into plain text."""
    if isinstance(response, str):
        return response
    if isinstance(response, list):
        return extract_text_from_messages(response)
    return str(response)


def extract_text_from_messages(messages: list[object]) -> str:
    """Extract text from a list of message dicts, keeping only assistant turns."""
    parts: list[str] = []
    for item in messages:
        if isinstance(item, dict) and item.get("role") == "assistant":
            collect_assistant_text(item, parts)
    return "\n".join(parts)


def collect_assistant_text(item: dict[str, object], parts: list[str]) -> None:
    """Append text from a single assistant message dict into parts."""
    content = item.get("content")
    if isinstance(content, str):
        parts.append(content)
    elif isinstance(content, list):
        collect_content_block_text(content, parts)


def collect_content_block_text(content: list[object], parts: list[str]) -> None:
    """Append text from content blocks of recognised types into parts."""
    text_block_types = {"text", "output_text", "input_text"}
    for block in content:
        if not isinstance(block, dict):
            continue
        if str(block.get("type", "")).lower() not in text_block_types:
            continue
        text = block.get("text")
        if isinstance(text, str) and text:
            parts.append(text)
