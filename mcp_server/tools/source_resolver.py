"""
Source Resolution Utilities

Resolves GraphRAG context sources (text unit IDs) to meaningful document
references with titles and text previews for agent consumption.

GraphRAG's context["sources"] DataFrame contains human_readable_id values
(e.g., '0', '7') that are meaningless without document mapping. This module
traces the full chain:

  context["sources"]["id"] (str)
    → text_units["human_readable_id"] (int64)
    → text_units["document_id"] (hash)
    → documents["id"] (hash) → documents["title"] (e.g., 'project_alpha.md')
"""

from __future__ import annotations

import pandas as pd

from core.data_loader import GraphData

# Maximum characters for text preview in source entries
TEXT_PREVIEW_LENGTH = 200


def resolve_sources(
    sources_df: pd.DataFrame | None,
    data: GraphData,
) -> list[dict]:
    """
    Resolve context source IDs to document titles and text previews.

    Args:
        sources_df: DataFrame from context["sources"] with 'id' and 'text' columns.
            The 'id' column contains human_readable_id values as strings.
        data: GraphData with text_units and documents loaded.

    Returns:
        List of dicts with 'document', 'text_preview', and 'text_unit_id' keys.
        Falls back to raw IDs if document mapping is unavailable.
    """
    if sources_df is None or sources_df.empty:
        return []

    if "id" not in sources_df.columns:
        return []

    # Build text_unit human_readable_id → document_id lookup
    tu_to_doc: dict[int, str] = {}
    if data.text_units is not None and not data.text_units.empty:
        for _, row in data.text_units.iterrows():
            hrid = row.get("human_readable_id")
            doc_id = row.get("document_id")
            if hrid is not None and doc_id is not None:
                tu_to_doc[int(hrid)] = str(doc_id)

    # Build document hash → title lookup
    doc_to_title: dict[str, str] = {}
    if data.documents is not None and not data.documents.empty:
        for _, row in data.documents.iterrows():
            doc_id = row.get("id")
            title = row.get("title")
            if doc_id is not None and title is not None:
                doc_to_title[str(doc_id)] = str(title)

    has_mapping = bool(tu_to_doc and doc_to_title)

    results: list[dict] = []
    seen_docs: set[str] = set()

    for _, src_row in sources_df.iterrows():
        src_id = src_row.get("id")
        src_text = src_row.get("text", "")

        # Create text preview
        text_str = str(src_text) if src_text else ""
        preview = text_str[:TEXT_PREVIEW_LENGTH]
        if len(text_str) > TEXT_PREVIEW_LENGTH:
            preview += "..."

        entry: dict = {"text_unit_id": str(src_id)}

        if has_mapping:
            try:
                hrid = int(src_id)
                doc_hash = tu_to_doc.get(hrid)
                if doc_hash:
                    title = doc_to_title.get(doc_hash, "unknown")
                    entry["document"] = title
                else:
                    entry["document"] = "unknown"
            except (ValueError, TypeError):
                entry["document"] = "unknown"
        
        if preview:
            entry["text_preview"] = preview

        results.append(entry)
        if "document" in entry:
            seen_docs.add(entry["document"])

    return results


def get_unique_documents(sources: list[dict]) -> list[str]:
    """Extract unique document names from resolved sources."""
    docs = []
    seen: set[str] = set()
    for src in sources:
        doc = src.get("document", "")
        if doc and doc != "unknown" and doc not in seen:
            docs.append(doc)
            seen.add(doc)
    return docs
