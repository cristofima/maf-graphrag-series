"""Unit tests for core/data_loader.py utility functions.

Most tests here are pure-function tests using in-memory GraphData with mock
DataFrames — no disk I/O. ``load_parquet``/``load_all`` tests use ``tmp_path``
with real (tiny) Parquet files written via pandas — no Azure/GraphRAG calls.
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest

from core.data_loader import (
    GraphData,
    get_community_count,
    get_entity_count,
    get_relationship_count,
    list_entities,
    list_entity_types,
    load_all,
    load_parquet,
)

REQUIRED_FILES = (
    "entities.parquet",
    "relationships.parquet",
    "communities.parquet",
    "community_reports.parquet",
    "text_units.parquet",
)


def _write_required_parquet_files(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_FILES:
        pd.DataFrame({"id": [1, 2]}).to_parquet(output_dir / name)


def _make_graph_data(
    entities: pd.DataFrame | None = None,
    relationships: pd.DataFrame | None = None,
    communities: pd.DataFrame | None = None,
) -> GraphData:
    return GraphData(
        entities=entities if entities is not None else pd.DataFrame(),
        relationships=relationships if relationships is not None else pd.DataFrame(),
        communities=communities if communities is not None else pd.DataFrame(),
        community_reports=pd.DataFrame(),
        text_units=pd.DataFrame(),
    )


class TestGraphDataCounts:
    def test_get_entity_count(self):
        entities = pd.DataFrame({"title": ["A", "B", "C"]})
        data = _make_graph_data(entities=entities)
        assert get_entity_count(data) == 3

    def test_get_relationship_count(self):
        relationships = pd.DataFrame({"source": ["A", "B"]})
        data = _make_graph_data(relationships=relationships)
        assert get_relationship_count(data) == 2

    def test_get_community_count(self):
        communities = pd.DataFrame({"id": ["c1", "c2"]})
        data = _make_graph_data(communities=communities)
        assert get_community_count(data) == 2

    def test_empty_dataframes_return_zero(self):
        data = _make_graph_data()
        assert get_entity_count(data) == 0
        assert get_relationship_count(data) == 0
        assert get_community_count(data) == 0

    def test_entity_count_single_row(self):
        data = _make_graph_data(entities=pd.DataFrame({"title": ["Solo"]}))
        assert get_entity_count(data) == 1


class TestListEntities:
    def test_returns_titles_from_title_column(self):
        entities = pd.DataFrame({"title": ["Alpha", "Beta", "Gamma"]})
        data = _make_graph_data(entities=entities)
        result = list_entities(data, limit=10)
        assert result == ["Alpha", "Beta", "Gamma"]

    def test_falls_back_to_name_column(self):
        entities = pd.DataFrame({"name": ["Alice", "Bob"]})
        data = _make_graph_data(entities=entities)
        result = list_entities(data, limit=10)
        assert result == ["Alice", "Bob"]

    def test_limit_restricts_output(self):
        entities = pd.DataFrame({"title": ["A", "B", "C", "D", "E"]})
        data = _make_graph_data(entities=entities)
        result = list_entities(data, limit=3)
        assert len(result) == 3
        assert result == ["A", "B", "C"]

    def test_default_limit_is_twenty(self):
        entities = pd.DataFrame({"title": [f"E{i}" for i in range(25)]})
        data = _make_graph_data(entities=entities)
        result = list_entities(data)
        assert len(result) == 20

    def test_no_known_column_returns_empty_list(self):
        entities = pd.DataFrame({"unknown_col": ["X", "Y"]})
        data = _make_graph_data(entities=entities)
        assert list_entities(data) == []

    def test_empty_dataframe_returns_empty_list(self):
        data = _make_graph_data()
        assert list_entities(data) == []


class TestListEntityTypes:
    def test_returns_unique_types(self):
        entities = pd.DataFrame({"type": ["person", "project", "person", "organization"]})
        data = _make_graph_data(entities=entities)
        result = list_entity_types(data)
        assert set(result) == {"person", "project", "organization"}

    def test_single_type_returns_list_with_one_entry(self):
        entities = pd.DataFrame({"type": ["person", "person"]})
        data = _make_graph_data(entities=entities)
        result = list_entity_types(data)
        assert result == ["person"]

    def test_no_type_column_returns_empty_list(self):
        entities = pd.DataFrame({"title": ["A"]})
        data = _make_graph_data(entities=entities)
        assert list_entity_types(data) == []

    def test_empty_entities_returns_empty_list(self):
        data = _make_graph_data()
        assert list_entity_types(data) == []


class TestGraphDataRepr:
    def test_repr_includes_row_counts(self):
        data = _make_graph_data(
            entities=pd.DataFrame({"title": ["A", "B"]}),
            relationships=pd.DataFrame({"id": ["r1"]}),
        )
        repr_str = repr(data)
        assert "entities=2 rows" in repr_str
        assert "relationships=1 rows" in repr_str

    def test_repr_shows_zero_for_empty_dataframes(self):
        data = _make_graph_data()
        repr_str = repr(data)
        assert "entities=0 rows" in repr_str


class TestLoadParquet:
    def test_raises_when_file_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="entities.parquet"):
            load_parquet("entities.parquet", tmp_path)

    def test_loads_dataframe_from_output_dir(self, tmp_path):
        pd.DataFrame({"title": ["Alpha", "Beta"]}).to_parquet(tmp_path / "entities.parquet")

        result = load_parquet("entities.parquet", tmp_path)

        assert list(result["title"]) == ["Alpha", "Beta"]

    def test_uses_get_output_dir_when_output_dir_not_given(self, monkeypatch, tmp_path):
        pd.DataFrame({"title": ["Solo"]}).to_parquet(tmp_path / "entities.parquet")
        monkeypatch.setattr("core.data_loader.get_output_dir", lambda: tmp_path)

        result = load_parquet("entities.parquet")

        assert list(result["title"]) == ["Solo"]


class TestLoadAll:
    def test_validate_true_calls_validate_output_files(self, monkeypatch, tmp_path):
        _write_required_parquet_files(tmp_path)
        mock_validate = MagicMock(return_value=True)
        monkeypatch.setattr("core.data_loader.validate_output_files", mock_validate)

        load_all(output_dir=tmp_path, validate=True)

        mock_validate.assert_called_once()

    def test_validate_false_skips_validation(self, monkeypatch, tmp_path):
        _write_required_parquet_files(tmp_path)
        mock_validate = MagicMock()
        monkeypatch.setattr("core.data_loader.validate_output_files", mock_validate)

        load_all(output_dir=tmp_path, validate=False)

        mock_validate.assert_not_called()

    def test_uses_get_output_dir_when_output_dir_not_given(self, monkeypatch, tmp_path):
        _write_required_parquet_files(tmp_path)
        monkeypatch.setattr("core.data_loader.get_output_dir", lambda: tmp_path)
        monkeypatch.setattr("core.data_loader.validate_output_files", MagicMock())

        data = load_all(validate=False)

        assert len(data.entities) == 2

    def test_loads_all_required_dataframes(self, tmp_path):
        _write_required_parquet_files(tmp_path)

        data = load_all(output_dir=tmp_path, validate=False)

        assert isinstance(data, GraphData)
        assert len(data.entities) == 2
        assert len(data.relationships) == 2
        assert len(data.communities) == 2
        assert len(data.community_reports) == 2
        assert len(data.text_units) == 2

    def test_covariates_and_documents_default_to_none(self, tmp_path):
        _write_required_parquet_files(tmp_path)

        data = load_all(output_dir=tmp_path, validate=False)

        assert data.covariates is None
        assert data.documents is None

    def test_loads_optional_covariates_when_present(self, tmp_path):
        _write_required_parquet_files(tmp_path)
        pd.DataFrame({"id": [1]}).to_parquet(tmp_path / "covariates.parquet")

        data = load_all(output_dir=tmp_path, validate=False)

        assert data.covariates is not None
        assert len(data.covariates) == 1

    def test_loads_optional_documents_when_present(self, tmp_path):
        _write_required_parquet_files(tmp_path)
        pd.DataFrame({"title": ["doc1.md"]}).to_parquet(tmp_path / "documents.parquet")

        data = load_all(output_dir=tmp_path, validate=False)

        assert data.documents is not None
        assert list(data.documents["title"]) == ["doc1.md"]
