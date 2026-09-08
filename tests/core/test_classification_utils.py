"""Unit tests for core/classification_utils.py."""

from maf_graphrag.core.classification_utils import normalize_confidence_score


class TestNormalizeConfidenceScore:
    def test_accepts_int_in_range(self) -> None:
        assert normalize_confidence_score(0) == 0
        assert normalize_confidence_score(100) == 100

    def test_rejects_int_out_of_range(self) -> None:
        assert normalize_confidence_score(-1) is None
        assert normalize_confidence_score(101) is None

    def test_accepts_only_integral_float_values(self) -> None:
        assert normalize_confidence_score(75.0) == 75
        assert normalize_confidence_score(75.5) is None

    def test_accepts_numeric_strings(self) -> None:
        assert normalize_confidence_score(" 42 ") == 42
        assert normalize_confidence_score("001") == 1

    def test_maps_legacy_labels(self) -> None:
        assert normalize_confidence_score("high") == 90
        assert normalize_confidence_score("MEDIUM") == 70
        assert normalize_confidence_score("Low") == 40

    def test_rejects_bool_and_unknown_values(self) -> None:
        assert normalize_confidence_score(True) is None
        assert normalize_confidence_score(False) is None
        assert normalize_confidence_score("unknown") is None
        assert normalize_confidence_score(object()) is None
