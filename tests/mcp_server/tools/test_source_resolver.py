"""Unit tests for mcp_server/tools/source_resolver.py — resolve_sources and get_unique_documents.

These are pure-function tests using in-memory pandas DataFrames.
No external services or disk I/O involved — fully deterministic.
"""

import pandas as pd

from core.data_loader import GraphData
from mcp_server.tools.source_resolver import TEXT_PREVIEW_LENGTH, get_unique_documents, resolve_sources


def _make_graph_data(
    text_units: pd.DataFrame | None = None,
    documents: pd.DataFrame | None = None,
) -> GraphData:
    """Build a minimal GraphData for source resolver tests."""
    return GraphData(
        entities=pd.DataFrame(),
        relationships=pd.DataFrame(),
        communities=pd.DataFrame(),
        community_reports=pd.DataFrame(),
        text_units=text_units if text_units is not None else pd.DataFrame(),
        documents=documents,
    )


class TestResolveSources:
    def test_none_sources_returns_empty_list(self):
        data = _make_graph_data()
        assert resolve_sources(None, data) == []

    def test_empty_dataframe_returns_empty_list(self):
        data = _make_graph_data()
        assert resolve_sources(pd.DataFrame(), data) == []

    def test_missing_id_column_returns_empty_list(self):
        sources_df = pd.DataFrame({"text": ["some text"]})
        data = _make_graph_data()
        assert resolve_sources(sources_df, data) == []

    def test_resolves_to_document_title(self):
        sources_df = pd.DataFrame({"id": ["0"], "text": ["chunk text"]})
        text_units = pd.DataFrame({"human_readable_id": [0], "document_id": ["doc-hash-1"]})
        documents = pd.DataFrame({"id": ["doc-hash-1"], "title": ["project_alpha.md"]})
        data = _make_graph_data(text_units=text_units, documents=documents)

        result = resolve_sources(sources_df, data)

        assert len(result) == 1
        assert result[0]["document"] == "project_alpha.md"
        assert result[0]["text_unit_id"] == "0"

    def test_text_unit_id_always_present(self):
        sources_df = pd.DataFrame({"id": ["7"], "text": ["text"]})
        data = _make_graph_data()

        result = resolve_sources(sources_df, data)

        assert result[0]["text_unit_id"] == "7"

    def test_text_preview_included_when_text_present(self):
        sources_df = pd.DataFrame({"id": ["0"], "text": ["Hello World"]})
        data = _make_graph_data()

        result = resolve_sources(sources_df, data)

        assert result[0]["text_preview"] == "Hello World"

    def test_text_preview_truncated_at_limit(self):
        long_text = "x" * (TEXT_PREVIEW_LENGTH + 50)
        sources_df = pd.DataFrame({"id": ["0"], "text": [long_text]})
        data = _make_graph_data()

        result = resolve_sources(sources_df, data)

        assert result[0]["text_preview"].endswith("...")
        assert len(result[0]["text_preview"]) == TEXT_PREVIEW_LENGTH + 3  # +3 for "..."

    def test_text_exactly_at_limit_is_not_truncated(self):
        exact_text = "y" * TEXT_PREVIEW_LENGTH
        sources_df = pd.DataFrame({"id": ["0"], "text": [exact_text]})
        data = _make_graph_data()

        result = resolve_sources(sources_df, data)

        assert not result[0]["text_preview"].endswith("...")
        assert len(result[0]["text_preview"]) == TEXT_PREVIEW_LENGTH

    def test_unknown_document_when_id_not_in_mapping(self):
        sources_df = pd.DataFrame({"id": ["99"], "text": ["text"]})
        text_units = pd.DataFrame({"human_readable_id": [0], "document_id": ["doc-hash-1"]})
        documents = pd.DataFrame({"id": ["doc-hash-1"], "title": ["alpha.md"]})
        data = _make_graph_data(text_units=text_units, documents=documents)

        result = resolve_sources(sources_df, data)

        assert result[0]["document"] == "unknown"

    def test_document_key_absent_when_no_mapping_data(self):
        """Without text_units or documents, 'document' key should not appear."""
        sources_df = pd.DataFrame({"id": ["0"], "text": ["text"]})
        data = _make_graph_data()  # empty text_units, no documents

        result = resolve_sources(sources_df, data)

        assert "document" not in result[0]

    def test_multiple_sources_all_resolved(self):
        sources_df = pd.DataFrame({"id": ["0", "1"], "text": ["text A", "text B"]})
        text_units = pd.DataFrame({"human_readable_id": [0, 1], "document_id": ["hash-a", "hash-b"]})
        documents = pd.DataFrame({"id": ["hash-a", "hash-b"], "title": ["alpha.md", "beta.md"]})
        data = _make_graph_data(text_units=text_units, documents=documents)

        result = resolve_sources(sources_df, data)

        assert len(result) == 2
        assert result[0]["document"] == "alpha.md"
        assert result[1]["document"] == "beta.md"

    def test_two_sources_same_document_both_included(self):
        """Both text units from the same doc are returned (dedup is handled by get_unique_documents)."""
        sources_df = pd.DataFrame({"id": ["0", "1"], "text": ["chunk A", "chunk B"]})
        text_units = pd.DataFrame({"human_readable_id": [0, 1], "document_id": ["same-hash", "same-hash"]})
        documents = pd.DataFrame({"id": ["same-hash"], "title": ["shared.md"]})
        data = _make_graph_data(text_units=text_units, documents=documents)

        result = resolve_sources(sources_df, data)

        assert len(result) == 2
        assert result[0]["document"] == "shared.md"
        assert result[1]["document"] == "shared.md"


class TestGetUniqueDocuments:
    def test_empty_list_returns_empty(self):
        assert get_unique_documents([]) == []

    def test_single_document_returned(self):
        sources = [{"document": "alpha.md", "text_unit_id": "0"}]
        assert get_unique_documents(sources) == ["alpha.md"]

    def test_deduplicates_same_document(self):
        sources = [
            {"document": "alpha.md", "text_unit_id": "0"},
            {"document": "alpha.md", "text_unit_id": "1"},
            {"document": "beta.md", "text_unit_id": "2"},
        ]
        result = get_unique_documents(sources)
        assert result == ["alpha.md", "beta.md"]

    def test_excludes_unknown_documents(self):
        sources = [
            {"document": "unknown", "text_unit_id": "0"},
            {"document": "alpha.md", "text_unit_id": "1"},
        ]
        result = get_unique_documents(sources)
        assert "unknown" not in result
        assert result == ["alpha.md"]

    def test_excludes_empty_document_names(self):
        sources = [{"document": "", "text_unit_id": "0"}]
        assert get_unique_documents(sources) == []

    def test_sources_without_document_key_ignored(self):
        sources = [{"text_unit_id": "0"}, {"document": "alpha.md", "text_unit_id": "1"}]
        result = get_unique_documents(sources)
        assert result == ["alpha.md"]

    def test_preserves_insertion_order(self):
        sources = [
            {"document": "beta.md"},
            {"document": "alpha.md"},
            {"document": "gamma.md"},
        ]
        result = get_unique_documents(sources)
        assert result == ["beta.md", "alpha.md", "gamma.md"]
