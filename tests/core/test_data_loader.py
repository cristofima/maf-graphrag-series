"""Unit tests for core/data_loader.py utility functions.

These are pure-function tests using in-memory GraphData with mock DataFrames.
No disk I/O — fully deterministic.
"""

import pandas as pd

from core.data_loader import (
    GraphData,
    get_community_count,
    get_entity_count,
    get_relationship_count,
    list_entities,
    list_entity_types,
)


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
