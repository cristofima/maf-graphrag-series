"""
Relationship Validity Evaluator.

Custom GraphRAG-specific evaluator that validates whether relationships
mentioned in agent responses correspond to actual relationships in the
knowledge graph Parquet data store.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


class RelationshipValidityEvaluator:
    """Validate that relationships in agent responses exist in the knowledge graph.

    Cross-references entity pairs mentioned together in model output against
    the actual Parquet relationship store built by GraphRAG indexing.

    Args:
        relationships_parquet_path: Path to the GraphRAG relationships Parquet file.
        entities_parquet_path: Path to the GraphRAG entities Parquet file (for entity name lookup).
    """

    def __init__(self, relationships_parquet_path: str, entities_parquet_path: str) -> None:
        rels_df = pd.read_parquet(relationships_parquet_path, columns=["source", "target"])
        self.valid_relationships: set[tuple[str, str]] = set()
        for _, row in rels_df.iterrows():
            src = str(row["source"]).lower()
            tgt = str(row["target"]).lower()
            self.valid_relationships.add((src, tgt))
            self.valid_relationships.add((tgt, src))  # bidirectional

        entities_df = pd.read_parquet(entities_parquet_path)
        entity_col = _resolve_entity_name_column(entities_df)
        self.known_entities: set[str] = set(entities_df[entity_col].astype(str).str.lower().tolist())

    def __call__(self, *, response: object, **kwargs: object) -> dict[str, Any]:
        """Evaluate relationship validity in a response.

        Args:
            response: The agent response to evaluate.

        Returns:
            Dict with relationship_validity score (0.0-1.0), valid/invalid pairs,
            and total counts.
        """
        response_text = _coerce_response_text(response)
        entity_mentions = self._extract_entity_mentions(response_text)

        # Find pairs of entities that appear close together (within same sentence)
        pairs = self._find_entity_pairs(response_text, entity_mentions)

        if not pairs:
            return {
                "relationship_validity": 1.0,
                "relationship_validity_result": "pass",
                "valid_relationships": [],
                "invalid_relationships": [],
                "total_pairs_checked": 0,
            }

        valid = [(s, t) for s, t in pairs if (s.lower(), t.lower()) in self.valid_relationships]
        invalid = [(s, t) for s, t in pairs if (s.lower(), t.lower()) not in self.valid_relationships]

        validity = len(valid) / len(pairs)
        result = "pass" if validity >= 0.5 else "fail"

        return {
            "relationship_validity": round(validity, 4),
            "relationship_validity_result": result,
            "valid_relationships": [list(p) for p in valid],
            "invalid_relationships": [list(p) for p in invalid],
            "total_pairs_checked": len(pairs),
        }

    def _extract_entity_mentions(self, text: str) -> list[str]:
        """Extract entity mentions that are known in the knowledge graph."""
        # Match capitalized phrases
        phrases = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text)
        return [p for p in phrases if p.lower() in self.known_entities]

    @staticmethod
    def _find_entity_pairs(text: str, entities: list[str]) -> list[tuple[str, str]]:
        """Find pairs of entities that appear in the same sentence."""
        sentences = re.split(r"[.!?]\n", text)
        pairs: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for sentence in sentences:
            in_sentence = [e for e in entities if e in sentence]
            for i, e1 in enumerate(in_sentence):
                for e2 in in_sentence[i + 1 :]:
                    if e1.lower() != e2.lower():
                        pair = (e1, e2)
                        normalized = tuple(sorted([e1.lower(), e2.lower()]))
                        if normalized not in seen:
                            seen.add(normalized)
                            pairs.append(pair)

        return pairs


def _resolve_entity_name_column(entities_df: pd.DataFrame) -> str:
    """Resolve the entity text column across GraphRAG schema versions."""
    if "name" in entities_df.columns:
        return "name"
    if "title" in entities_df.columns:
        return "title"
    raise ValueError("Entities parquet must contain either 'name' or 'title' column.")


def _coerce_response_text(response: object) -> str:
    """Convert evaluator response payloads into plain text."""
    if isinstance(response, str):
        return response

    if isinstance(response, list):
        parts: list[str] = []
        for item in response:
            if not isinstance(item, dict):
                continue
            if item.get("role") != "assistant":
                continue

            content = item.get("content")
            if isinstance(content, str):
                parts.append(content)
                continue

            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    block_type = str(block.get("type", "")).lower()
                    if block_type in {"text", "output_text", "input_text"}:
                        text = block.get("text")
                        if isinstance(text, str) and text:
                            parts.append(text)

        return "\n".join(parts)

    return str(response)
