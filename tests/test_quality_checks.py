"""
test_quality_checks.py
Unit tests for data quality validation utilities.
"""
import pandas as pd

from src.utils.quality_checks import (
    validate_schema,
    check_completeness,
    check_duplicates,
    check_value_range,
)


class TestSchemaValidation:
    def test_valid_schema(self):
        df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        assert validate_schema(df, ["a", "b"]) is True

    def test_missing_columns(self):
        df = pd.DataFrame({"a": [1]})
        assert validate_schema(df, ["a", "b"]) is False


class TestCompleteness:
    def test_full_completeness(self):
        df = pd.DataFrame({"id": [1, 2, 3]})
        assert check_completeness(df, "id", threshold=0.95) is True

    def test_below_threshold(self):
        df = pd.DataFrame({"id": [1, None, None, None, 5]})
        assert check_completeness(df, "id", threshold=0.95) is False

    def test_exact_threshold(self):
        df = pd.DataFrame({"id": list(range(95)) + [None] * 5})
        assert check_completeness(df, "id", threshold=0.95) is True


class TestDuplicates:
    def test_no_duplicates(self):
        df = pd.DataFrame({"id": [1, 2, 3, 4, 5]})
        assert check_duplicates(df, "id") is True

    def test_high_duplicate_rate(self):
        df = pd.DataFrame({"id": [1, 1, 1, 1, 5]})
        assert check_duplicates(df, "id", max_dup_rate=0.01) is False


class TestValueRange:
    def test_within_range(self):
        df = pd.DataFrame({"price": [5.0, 10.0, 15.0]})
        assert check_value_range(df, "price", min_val=0, max_val=100) is True

    def test_below_min(self):
        df = pd.DataFrame({"price": [-5.0, 10.0]})
        assert check_value_range(df, "price", min_val=0) is False

    def test_above_max(self):
        df = pd.DataFrame({"price": [5.0, 999999.0]})
        assert check_value_range(df, "price", max_val=1000) is False
