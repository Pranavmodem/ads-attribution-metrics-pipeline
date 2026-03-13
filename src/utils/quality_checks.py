"""
quality_checks.py
Data quality validation utilities for the attribution pipeline.

Runs checks at ingestion time and as standalone quality gates.
"""
import logging
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def validate_schema(df: pd.DataFrame, required_columns: List[str]) -> bool:
    """Check that all required columns are present."""
    missing = set(required_columns) - set(df.columns)
    if missing:
        logger.error(f"Schema validation failed. Missing columns: {missing}")
        return False
    return True


def check_completeness(df: pd.DataFrame, key_column: str, threshold: float = 0.95) -> bool:
    """Check that the key column is non-null above the threshold.

    Args:
        df: Input dataframe.
        key_column: Column to check for completeness.
        threshold: Minimum non-null ratio (default 95%).

    Returns:
        True if completeness is above threshold.
    """
    non_null_ratio = df[key_column].notna().mean()
    passed = non_null_ratio >= threshold
    status = "PASS" if passed else "FAIL"
    logger.info(
        f"Completeness check [{status}]: {key_column} = {non_null_ratio:.2%} "
        f"(threshold: {threshold:.2%})"
    )
    return passed


def check_freshness(df: pd.DataFrame, timestamp_col: str, max_delay_hours: int = 24) -> bool:
    """Check that the most recent record is within the expected delay window."""
    max_ts = pd.to_datetime(df[timestamp_col]).max()
    now = pd.Timestamp.now(tz="UTC")
    delay_hours = (now - max_ts).total_seconds() / 3600

    passed = delay_hours <= max_delay_hours
    status = "PASS" if passed else "FAIL"
    logger.info(
        f"Freshness check [{status}]: latest record is {delay_hours:.1f} hours old "
        f"(max allowed: {max_delay_hours}h)"
    )
    return passed


def check_duplicates(df: pd.DataFrame, key_column: str, max_dup_rate: float = 0.01) -> bool:
    """Check that duplicate rate on key column is below threshold."""
    total = len(df)
    unique = df[key_column].nunique()
    dup_rate = 1 - (unique / total) if total > 0 else 0

    passed = dup_rate <= max_dup_rate
    status = "PASS" if passed else "FAIL"
    logger.info(
        f"Duplicate check [{status}]: {key_column} dup rate = {dup_rate:.4%} "
        f"(max allowed: {max_dup_rate:.2%})"
    )
    return passed


def check_value_range(
    df: pd.DataFrame, column: str, min_val: Optional[float] = None, max_val: Optional[float] = None
) -> bool:
    """Check that numeric values fall within expected range."""
    col_min = df[column].min()
    col_max = df[column].max()

    issues = []
    if min_val is not None and col_min < min_val:
        issues.append(f"min={col_min} < expected min={min_val}")
    if max_val is not None and col_max > max_val:
        issues.append(f"max={col_max} > expected max={max_val}")

    passed = len(issues) == 0
    status = "PASS" if passed else "FAIL"
    logger.info(f"Range check [{status}]: {column} range=[{col_min}, {col_max}] {', '.join(issues)}")
    return passed


def run_all_quality_checks(df: pd.DataFrame, entity: str) -> dict:
    """Run standard quality check suite for a given entity."""
    logger.info(f"Running quality checks for {entity} ({len(df):,} records)")

    checks = {}
    if entity == "impressions":
        checks["schema"] = validate_schema(df, ["impression_id", "timestamp", "campaign_id"])
        checks["completeness"] = check_completeness(df, "impression_id")
        checks["duplicates"] = check_duplicates(df, "impression_id")
        checks["bid_range"] = check_value_range(df, "bid_price_usd", min_val=0, max_val=1000)
        checks["freshness"] = check_freshness(df, "timestamp")
    elif entity == "conversions":
        checks["schema"] = validate_schema(df, ["conversion_id", "timestamp", "user_id"])
        checks["completeness"] = check_completeness(df, "conversion_id")
        checks["duplicates"] = check_duplicates(df, "conversion_id")
        checks["revenue_range"] = check_value_range(df, "revenue_usd", min_val=-100, max_val=50000)

    all_passed = all(checks.values())
    logger.info(f"Quality checks {'ALL PASSED' if all_passed else 'SOME FAILED'}: {checks}")
    return checks
