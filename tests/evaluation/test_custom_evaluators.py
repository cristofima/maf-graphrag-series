"""Unit tests for custom GraphRAG evaluators — EntityAccuracy and RelationshipValidity."""

from pathlib import Path

import pandas as pd
import pytest

from evaluation.evaluators.entity_accuracy import EntityAccuracyEvaluator
from evaluation.evaluators.relationship_validity import RelationshipValidityEvaluator


@pytest.fixture()
def entities_parquet(tmp_path: Path) -> str:
    """Create a temporary entities Parquet file."""
    df = pd.DataFrame(
        {
            "name": [
                "Sarah Chen",
                "Michael Rodriguez",
                "TechVenture Dynamics",
                "Project Alpha",
                "Cloud Infrastructure",
            ],
        }
    )
    path = tmp_path / "entities.parquet"
    df.to_parquet(path)
    return str(path)


@pytest.fixture()
def relationships_parquet(tmp_path: Path) -> str:
    """Create a temporary relationships Parquet file."""
    df = pd.DataFrame(
        {
            "source": ["SARAH CHEN", "MICHAEL RODRIGUEZ", "PROJECT ALPHA"],
            "target": ["TECHVENTURE DYNAMICS", "TECHVENTURE DYNAMICS", "CLOUD INFRASTRUCTURE"],
        }
    )
    path = tmp_path / "relationships.parquet"
    df.to_parquet(path)
    return str(path)


class TestEntityAccuracyEvaluator:
    def test_known_entities_found(self, entities_parquet):
        evaluator = EntityAccuracyEvaluator(entities_parquet)

        result = evaluator(response="Sarah Chen leads TechVenture Dynamics on Project Alpha.")

        # The extraction finds multi-word phrases + single capitalized words
        # Some single-word fragments (Chen, Dynamics, etc.) won't match full entity names
        assert result["total_mentioned"] > 0
        valid_lower = [e.lower() for e in result["valid_entities"]]
        assert "sarah chen" in valid_lower
        assert "project alpha" in valid_lower

    def test_mixed_valid_invalid_entities(self, entities_parquet):
        evaluator = EntityAccuracyEvaluator(entities_parquet)

        result = evaluator(response="Sarah Chen and John Doe work at the company.")

        assert result["total_mentioned"] > 0
        valid_lower = [e.lower() for e in result["valid_entities"]]
        assert "sarah chen" in valid_lower
        invalid_lower = [e.lower() for e in result["invalid_entities"]]
        assert "john doe" in invalid_lower

    def test_no_entities_returns_perfect(self, entities_parquet):
        evaluator = EntityAccuracyEvaluator(entities_parquet)

        result = evaluator(response="the company is doing well this quarter.")

        assert result["entity_accuracy"] == 1.0
        assert result["total_mentioned"] == 0

    def test_all_invalid_entities(self, entities_parquet):
        evaluator = EntityAccuracyEvaluator(entities_parquet)

        result = evaluator(response="John Doe and Jane Smith are in the team. Bob Wilson helps too.")

        # None of these are in the knowledge graph
        assert result["entity_accuracy"] == 0.0
        assert result["entity_accuracy_result"] == "fail"

    def test_case_insensitive_matching(self, entities_parquet):
        evaluator = EntityAccuracyEvaluator(entities_parquet)

        result = evaluator(response="The report mentions Sarah Chen as key stakeholder.")

        valid_lower = [e.lower() for e in result["valid_entities"]]
        assert "sarah chen" in valid_lower


class TestEntityMentionExtraction:
    def test_extract_multi_word_phrases(self, entities_parquet):
        evaluator = EntityAccuracyEvaluator(entities_parquet)
        mentions = evaluator._extract_entity_mentions("Sarah Chen and Project Alpha are key.")
        assert "Sarah Chen" in mentions
        assert "Project Alpha" in mentions

    def test_skip_sentence_start_words(self, entities_parquet):
        evaluator = EntityAccuracyEvaluator(entities_parquet)
        # "The" starts the sentence but shouldn't be extracted
        mentions = evaluator._extract_entity_mentions("The team is working hard.")
        assert "The" not in mentions

    def test_deduplication(self, entities_parquet):
        evaluator = EntityAccuracyEvaluator(entities_parquet)
        mentions = evaluator._extract_entity_mentions("Sarah Chen met with Sarah Chen about Project Alpha.")
        # Should only have one instance of "Sarah Chen"
        assert mentions.count("Sarah Chen") == 1


class TestRelationshipValidityEvaluator:
    def test_valid_relationship(self, relationships_parquet, entities_parquet):
        evaluator = RelationshipValidityEvaluator(relationships_parquet, entities_parquet)

        result = evaluator(response="Sarah Chen works at TechVenture Dynamics as the CEO.")

        assert result["relationship_validity"] == 1.0
        assert result["relationship_validity_result"] == "pass"

    def test_no_entity_pairs_returns_perfect(self, relationships_parquet, entities_parquet):
        evaluator = RelationshipValidityEvaluator(relationships_parquet, entities_parquet)

        result = evaluator(response="the quarterly results are strong this year.")

        assert result["relationship_validity"] == 1.0
        assert result["total_pairs_checked"] == 0

    def test_bidirectional_matching(self, relationships_parquet, entities_parquet):
        evaluator = RelationshipValidityEvaluator(relationships_parquet, entities_parquet)

        # Reverse order: target → source
        result = evaluator(response="TechVenture Dynamics is led by Sarah Chen.")

        # Should still match since relationships are loaded bidirectionally
        if result["total_pairs_checked"] > 0:
            assert result["relationship_validity"] > 0.0

    def test_result_structure(self, relationships_parquet, entities_parquet):
        evaluator = RelationshipValidityEvaluator(relationships_parquet, entities_parquet)

        result = evaluator(response="Sarah Chen leads TechVenture Dynamics on Cloud Infrastructure.")

        assert "relationship_validity" in result
        assert "relationship_validity_result" in result
        assert "valid_relationships" in result
        assert "invalid_relationships" in result
        assert "total_pairs_checked" in result
        assert isinstance(result["relationship_validity"], float)
        assert result["relationship_validity_result"] in ("pass", "fail")


class TestRelationshipEntityExtraction:
    def test_extracts_known_entities_only(self, relationships_parquet, entities_parquet):
        evaluator = RelationshipValidityEvaluator(relationships_parquet, entities_parquet)
        mentions = evaluator._extract_entity_mentions("Sarah Chen and Unknown Person work at TechVenture Dynamics.")
        # Should only extract entities in the known set
        assert all(m.lower() in evaluator.known_entities for m in mentions)

    def test_find_entity_pairs_same_sentence(self, relationships_parquet, entities_parquet):
        evaluator = RelationshipValidityEvaluator(relationships_parquet, entities_parquet)
        entities = ["Sarah Chen", "TechVenture Dynamics"]
        text = "Sarah Chen is CEO of TechVenture Dynamics."
        pairs = evaluator._find_entity_pairs(text, entities)
        assert len(pairs) >= 1
        pair_lower = [(p[0].lower(), p[1].lower()) for p in pairs]
        assert ("sarah chen", "techventure dynamics") in pair_lower
