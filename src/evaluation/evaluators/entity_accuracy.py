"""
Entity Accuracy Evaluator.

Custom GraphRAG-specific evaluator that validates whether entities
referenced in agent responses actually exist in the knowledge graph
Parquet data store.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


class EntityAccuracyEvaluator:
    """Validate that entities in agent responses exist in the knowledge graph.

    Cross-references entity mentions in model output against the actual
    Parquet entity store built by GraphRAG indexing.

    Args:
        entities_parquet_path: Path to the GraphRAG entities Parquet file.
    """

    def __init__(self, entities_parquet_path: str) -> None:
        entities_df = pd.read_parquet(entities_parquet_path)
        entity_col = _resolve_entity_name_column(entities_df)
        self.valid_entities: set[str] = set(entities_df[entity_col].astype(str).str.lower().tolist())

    def __call__(self, *, response: object, **kwargs: object) -> dict[str, Any]:
        """Evaluate entity accuracy in a response.

        Args:
            response: The agent response to evaluate.

        Returns:
            Dict with entity_accuracy score (0.0-1.0), valid/invalid entity lists,
            and total counts.
        """
        response_text = _coerce_response_text(response)
        mentioned = self._extract_entity_mentions(response_text)

        if not mentioned:
            return {
                "entity_accuracy": 1.0,
                "entity_accuracy_result": "pass",
                "valid_entities": [],
                "invalid_entities": [],
                "total_mentioned": 0,
            }

        valid = [e for e in mentioned if e.lower() in self.valid_entities]
        invalid = [e for e in mentioned if e.lower() not in self.valid_entities]

        accuracy = len(valid) / len(mentioned)
        result = "pass" if accuracy >= 0.5 else "fail"

        return {
            "entity_accuracy": round(accuracy, 4),
            "entity_accuracy_result": result,
            "valid_entities": valid,
            "invalid_entities": invalid,
            "total_mentioned": len(mentioned),
        }

    @staticmethod
    def _extract_entity_mentions(text: str) -> list[str]:
        """Extract likely entity mentions from response text.

        Uses heuristics based on GraphRAG's entity naming convention:
        capitalized multi-word phrases and single capitalized words > 2 chars
        that aren't common English words at sentence starts.
        """
        # Match capitalized phrases (e.g., "Project Alpha", "Alice Johnson")
        phrases = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)

        # Match single capitalized words (proper nouns), excluding sentence starts
        # Split by sentences, skip first word of each sentence
        sentences = re.split(r"[.!?]\s+", text)
        single_words: list[str] = []
        for sentence in sentences:
            words = sentence.split()
            for word in words[1:]:  # skip first word (sentence start)
                clean = word.strip(".,;:()\"'")
                if clean and clean[0].isupper() and len(clean) > 2 and not clean.isupper():
                    single_words.append(clean)

        # Combine and deduplicate while preserving order
        seen: set[str] = set()
        result: list[str] = []
        for entity in phrases + single_words:
            if entity.lower() not in seen:
                seen.add(entity.lower())
                result.append(entity)

        return result


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
