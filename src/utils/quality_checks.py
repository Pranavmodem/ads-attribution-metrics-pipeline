"""
quality_checks.py
Data quality gate for lake partitions, run between ingestion and dbt.

    python -m src.utils.quality_checks                    # every partition
    python -m src.utils.quality_checks --date 2026-11-13  # one day, as the DAG runs it

Exits 1 when any error-level check fails, so the orchestrator stops before dbt
builds on bad data. Warn-level checks are reported but never block. The full
report is written to data/quality/report.json for the dashboard.
"""
import argparse
import glob
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

from src.utils.config import PipelineConfig
from src.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


def _naive_utc(ts) -> pd.Series:
    """Timestamps as tz-naive UTC, whatever they came in as."""
    ts = pd.to_datetime(ts, utc=True)
    return ts.dt.tz_localize(None) if isinstance(ts, pd.Series) else ts.tz_localize(None)


def validate_schema(df: pd.DataFrame, required_columns: List[str]) -> bool:
    """Check that all required columns are present."""
    missing = set(required_columns) - set(df.columns)
    if missing:
        logger.error(f"Schema validation failed. Missing columns: {sorted(missing)}")
    return not missing


def completeness(df: pd.DataFrame, column: str) -> float:
    return float(df[column].notna().mean()) if len(df) else 1.0


def check_completeness(df: pd.DataFrame, key_column: str, threshold: float = 0.95) -> bool:
    """True when the non-null share of `key_column` is at least `threshold`."""
    return completeness(df, key_column) >= threshold


def hours_since_latest(df: pd.DataFrame, timestamp_col: str, as_of: Optional[datetime] = None) -> float:
    latest = _naive_utc(df[timestamp_col]).max()
    now = _naive_utc(pd.Timestamp(as_of or pd.Timestamp.now(tz="UTC")))
    return (now - latest).total_seconds() / 3600


def check_freshness(
    df: pd.DataFrame, timestamp_col: str, max_delay_hours: float = 24, as_of: Optional[datetime] = None
) -> bool:
    """True when the newest record is at most `max_delay_hours` older than `as_of` (default: now).

    Accepts tz-aware or tz-naive timestamps; naive ones are taken as UTC.
    """
    return hours_since_latest(df, timestamp_col, as_of) <= max_delay_hours


def duplicate_rate(df: pd.DataFrame, key_column: str) -> float:
    return 1 - df[key_column].nunique() / len(df) if len(df) else 0.0


def check_duplicates(df: pd.DataFrame, key_column: str, max_dup_rate: float = 0.01) -> bool:
    """True when the duplicate rate on `key_column` is at most `max_dup_rate`."""
    return duplicate_rate(df, key_column) <= max_dup_rate


def check_value_range(
    df: pd.DataFrame, column: str, min_val: Optional[float] = None, max_val: Optional[float] = None
) -> bool:
    """True when every value in `column` lies inside [min_val, max_val]."""
    ok = True
    if min_val is not None:
        ok &= bool(df[column].min() >= min_val)
    if max_val is not None:
        ok &= bool(df[column].max() <= max_val)
    return ok


@dataclass
class CheckResult:
    entity: str
    check: str
    passed: bool
    observed: str
    expected: str
    severity: str = "error"  # "warn" is reported but never fails the run


SCHEMAS = {
    "impressions": ["impression_id", "timestamp", "user_id", "campaign_id", "channel", "bid_price_usd"],
    "clicks": ["click_id", "impression_id", "timestamp", "user_id", "campaign_id"],
    "conversions": ["conversion_id", "timestamp", "received_at", "user_id", "revenue_usd"],
    "campaigns": ["campaign_id", "campaign_name", "channel"],
}
KEYS = {
    "impressions": "impression_id",
    "clicks": "click_id",
    "conversions": "conversion_id",
    "campaigns": "campaign_id",
}


def run_quality_checks(
    df: pd.DataFrame,
    entity: str,
    as_of: Optional[datetime] = None,
    daily_counts: Optional[pd.Series] = None,
) -> List[CheckResult]:
    """Run the check suite for one entity's lake data."""
    results: List[CheckResult] = []

    def add(check, passed, observed, expected, severity="error"):
        results.append(CheckResult(entity, check, bool(passed), observed, expected, severity))

    schema = SCHEMAS[entity]
    missing = sorted(set(schema) - set(df.columns))
    add("schema", not missing, f"missing {missing}" if missing else "all columns", ", ".join(schema))
    if missing:
        return results

    if entity == "campaigns":
        add("unique key", check_duplicates(df, "campaign_id", 0.0), f"{duplicate_rate(df, 'campaign_id'):.2%}", "0%")
        return results

    add("rows present", len(df) > 0, f"{len(df):,}", "> 0")
    if not len(df):
        return results
    key = KEYS[entity]
    worst = min(schema, key=lambda c: completeness(df, c))
    add("completeness", completeness(df, worst) >= 0.999,
        f"{completeness(df, worst):.2%} ({worst})", ">= 99.9% on every required column")
    add("unique key", check_duplicates(df, key, 0.0), f"{duplicate_rate(df, key):.2%} duplicate {key}", "0%")

    if entity == "impressions":
        add("CPM in range", check_value_range(df, "bid_price_usd", 0, 1000),
            f"${df['bid_price_usd'].min():.2f} to ${df['bid_price_usd'].max():.2f}", "$0 to $1,000")
    if entity == "conversions":
        add("revenue in range", check_value_range(df, "revenue_usd", 0, 5000),
            f"${df['revenue_usd'].min():.2f} to ${df['revenue_usd'].max():,.2f}", "$0 to $5,000")
        late = (_naive_utc(df["received_at"]) - _naive_utc(df["timestamp"])) > pd.Timedelta(hours=24)
        add("late arrivals", late.mean() <= 0.10, f"{late.mean():.1%} arrived > 24h late", "<= 10%", "warn")
        backwards = int((_naive_utc(df["timestamp"]) > _naive_utc(df["received_at"])).sum())
        add("received after it happened", backwards == 0, f"{backwards:,} rows received before their event",
            "0 rows")

    ts_col = "received_at" if entity == "conversions" else "timestamp"
    lag = hours_since_latest(df, ts_col, as_of)
    add("freshness", lag <= 26, f"newest row {lag:.1f}h old", "<= 26h", "error" if entity == "impressions" else "warn")

    if daily_counts is not None and len(daily_counts) >= 8:
        latest, history = daily_counts.iloc[-1], daily_counts.iloc[-15:-1]
        z = (latest - history.mean()) / history.std() if history.std() > 0 else 0.0
        add("volume vs trailing 14 days", abs(z) <= 3, f"{latest:,} rows (z = {z:+.1f})", "|z| <= 3", "warn")
    return results


def read_lake(entity: str, lake_root: str, partition_date: Optional[str] = None) -> pd.DataFrame:
    pattern = os.path.join(lake_root, entity, f"dt={partition_date}" if partition_date else "dt=*", "*.parquet")
    files = sorted(glob.glob(pattern))
    if not files:
        return pd.DataFrame(columns=SCHEMAS[entity])
    return pd.concat([pd.read_parquet(f).assign(dt=os.path.basename(os.path.dirname(f))[3:]) for f in files],
                     ignore_index=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Data quality gate for lake partitions")
    parser.add_argument("--date", help="Check one partition (YYYY-MM-DD). Default: all partitions.")
    parser.add_argument("--entity", choices=list(SCHEMAS), action="append", help="Default: all entities.")
    parser.add_argument("--report", default="data/quality/report.json")
    args = parser.parse_args(argv)
    setup_logging()
    config = PipelineConfig.from_env()

    # A daily run is judged as of the end of its partition day, not the wall clock.
    as_of = datetime.fromisoformat(args.date) + timedelta(days=1) if args.date else None
    results: List[CheckResult] = []
    for entity in args.entity or list(SCHEMAS):
        history = read_lake(entity, config.lake_root)
        df = history[history["dt"] == args.date] if args.date and len(history) else history
        counts = None
        if entity != "campaigns" and len(history):
            counts = history.groupby("dt").size().sort_index()
            if args.date:
                counts = counts[counts.index <= args.date]
        results += run_quality_checks(df, entity, as_of=as_of, daily_counts=counts)

    failed = [r for r in results if not r.passed and r.severity == "error"]
    warned = [r for r in results if not r.passed and r.severity == "warn"]
    for r in results:
        mark = "PASS" if r.passed else ("FAIL" if r.severity == "error" else "WARN")
        logger.info(f"[{mark}] {r.entity:<12} {r.check:<27} {r.observed}  (expected {r.expected})")

    os.makedirs(os.path.dirname(args.report) or ".", exist_ok=True)
    with open(args.report, "w") as f:
        json.dump({
            "checked_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "partition_date": args.date,
            "passed": not failed,
            "results": [asdict(r) for r in results],
        }, f, indent=2)
    logger.info(f"{len(results)} checks: {len(results) - len(failed) - len(warned)} passed, "
                f"{len(warned)} warned, {len(failed)} failed; report in {args.report}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
