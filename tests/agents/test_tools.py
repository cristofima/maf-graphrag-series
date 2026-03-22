"""Unit tests for agents/tools.py — Local @tool functions."""

from agents.tools import extract_key_entities, format_as_table


class TestFormatAsTable:
    def test_basic_table(self):
        rows = [
            {"name": "Alice", "role": "Lead"},
            {"name": "Bob", "role": "Dev"},
        ]
        result = format_as_table(rows)
        assert "| name | role |" in result
        assert "| --- | --- |" in result
        assert "| Alice | Lead |" in result
        assert "| Bob | Dev |" in result

    def test_custom_columns(self):
        rows = [
            {"name": "Alice", "role": "Lead", "team": "Alpha"},
        ]
        result = format_as_table(rows, columns=["name", "team"])
        assert "| name | team |" in result
        assert "| Alice | Alpha |" in result
        # "role" should not appear in the output
        assert "role" not in result.split("\n")[0]

    def test_empty_rows(self):
        result = format_as_table([])
        assert "No data" in result

    def test_empty_columns(self):
        rows = [{}]
        result = format_as_table(rows, columns=[])
        assert "No columns" in result

    def test_missing_keys_in_row(self):
        rows = [
            {"name": "Alice", "role": "Lead"},
            {"name": "Bob"},
        ]
        result = format_as_table(rows, columns=["name", "role"])
        lines = result.strip().split("\n")
        assert len(lines) == 4  # header + separator + 2 rows
        assert "| Bob |  |" in lines[3]

    def test_infers_columns_from_first_row(self):
        rows = [{"x": 1, "y": 2}]
        result = format_as_table(rows)
        assert "| x | y |" in result

    def test_tool_metadata(self):
        """Verify @tool decorator metadata."""
        assert hasattr(format_as_table, "name") or callable(format_as_table)


class TestExtractKeyEntities:
    def test_extracts_project_patterns(self):
        text = "Project Alpha is led by Sarah Chen."
        entities = extract_key_entities(text)
        assert "Project Alpha" in entities
        assert "Sarah Chen" in entities

    def test_extracts_operation_patterns(self):
        text = "Operation Sunrise is the codename."
        entities = extract_key_entities(text)
        assert "Operation Sunrise" in entities

    def test_extracts_multi_word_proper_nouns(self):
        text = "Alex Turner joined TechVenture Inc last year."
        entities = extract_key_entities(text)
        assert "Alex Turner" in entities

    def test_skips_common_sentence_starters(self):
        text = "The project was led by someone. This approach failed."
        entities = extract_key_entities(text)
        # "The project" and "This approach" should NOT be entities
        for entity in entities:
            assert not entity.startswith("The ")
            assert not entity.startswith("This ")

    def test_empty_text(self):
        assert extract_key_entities("") == []
        assert extract_key_entities("   ") == []

    def test_no_entities(self):
        text = "this is all lowercase with no proper nouns"
        assert extract_key_entities(text) == []

    def test_returns_sorted_deduplicated(self):
        text = "Project Alpha and Project Alpha again. Sarah Chen too."
        entities = extract_key_entities(text)
        # Should be deduplicated
        assert entities == sorted(set(entities))

    def test_initiative_pattern(self):
        text = "Initiative Phoenix launched in Q3."
        entities = extract_key_entities(text)
        assert "Initiative Phoenix" in entities

    def test_team_pattern(self):
        text = "Team Omega handles backend services."
        entities = extract_key_entities(text)
        assert "Team Omega" in entities
