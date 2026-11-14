"""
test_quality_checks.py
Check functions and the quality gate CLI.
"""
import os
from datetime import datetime, timedelta

import pandas as pd
import pytest

from src.utils import quality_checks as qc


class TestCheckFunctions:
    def test_schema(self):
        df = pd.DataFrame({"a": [1], "b": [2], "c": [3]})
        assert qc.validate_schema(df, ["a", "b"]) is True
        assert qc.validate_schema(df, ["a", "z"]) is False

    def test_completeness_returns_plain_bools(self):
        assert qc.check_completeness(pd.DataFrame({"id": [1, 2, 3]}), "id", 0.95) is True
        assert qc.check_completeness(pd.DataFrame({"id": [1, None, None, None, 5]}), "id", 0.95) is False
        exact = pd.DataFrame({"id": list(range(95)) + [None] * 5})
        assert qc.check_completeness(exact, "id", 0.95) is True

    def test_duplicates(self):
        df = pd.DataFrame({"id": [1, 2, 2, 3]})
        assert qc.check_duplicates(df, "id", max_dup_rate=0.0) is False
        assert qc.check_duplicates(df, "id", max_dup_rate=0.3) is True

    def test_value_range(self):
        df = pd.DataFrame({"v": [0.5, 10.0]})
        assert qc.check_value_range(df, "v", 0, 100) is True
        assert qc.check_value_range(df, "v", 1, 100) is False

    @pytest.mark.parametrize("tz", [None, "UTC"])
    def test_freshness_accepts_naive_and_aware_timestamps(self, tz):
        now = pd.Timestamp("2026-06-01 12:00")
        ts = pd.Series([now - timedelta(hours=30), now - timedelta(hours=3)])
        df = pd.DataFrame({"ts": ts.dt.tz_localize(tz) if tz else ts})
        assert qc.check_freshness(df, "ts", max_delay_hours=24, as_of=now) is True
        assert qc.check_freshness(df, "ts", max_delay_hours=2, as_of=now) is False


def _impressions(n=50, start=datetime(2026, 6, 1)):
    return pd.DataFrame({
        "impression_id": [f"imp_{i}" for i in range(n)],
        "timestamp": [start + timedelta(minutes=25 * i) for i in range(n)],
        "user_id": "u1",
        "campaign_id": "camp_0001",
        "channel": "Display",
        "bid_price_usd": 8.0,
    })


def test_suite_flags_duplicate_keys():
    df = pd.concat([_impressions(), _impressions().head(3)])
    results = {r.check: r for r in qc.run_quality_checks(df, "impressions", as_of=datetime(2026, 6, 2))}
    assert results["unique key"].passed is False
    assert results["completeness"].passed is True


def _write_lake(root, df):
    path = os.path.join(root, "impressions", "dt=2026-06-01")
    os.makedirs(path)
    df.to_parquet(os.path.join(path, "part-0.parquet"), index=False)


def test_cli_passes_clean_partition(tmp_path, monkeypatch):
    _write_lake(tmp_path, _impressions())
    monkeypatch.setenv("LAKE_ROOT", str(tmp_path))
    code = qc.main(["--date", "2026-06-01", "--entity", "impressions", "--report", str(tmp_path / "r.json")])
    assert code == 0


def test_cli_fails_on_bad_partition(tmp_path, monkeypatch):
    bad = pd.concat([_impressions(), _impressions().head(5)])
    bad.loc[0, "bid_price_usd"] = 5000.0
    _write_lake(tmp_path, bad)
    monkeypatch.setenv("LAKE_ROOT", str(tmp_path))
    code = qc.main(["--date", "2026-06-01", "--entity", "impressions", "--report", str(tmp_path / "r.json")])
    assert code == 1
