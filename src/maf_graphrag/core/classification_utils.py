"""Shared helpers for routing/classification parsing."""

from __future__ import annotations


def normalize_confidence_score(value: object) -> int | None:
    """Normalize confidence payload values into a bounded integer percentage."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if 0 <= value <= 100 else None
    if isinstance(value, float):
        integer = int(value)
        return integer if integer == value and 0 <= integer <= 100 else None
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    if stripped.isdigit():
        score = int(stripped)
        return score if 0 <= score <= 100 else None

    # Backward compatibility for legacy prompts/tests.
    legacy_scores = {
        "high": 90,
        "medium": 70,
        "low": 40,
    }
    return legacy_scores.get(stripped.lower())
