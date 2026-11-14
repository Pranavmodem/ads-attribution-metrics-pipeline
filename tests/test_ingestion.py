"""
test_ingestion.py
Loader: partitioning, deduplication, idempotency, and the audit trail.
"""
import glob
import json
import os

import pandas as pd
import pytest

from src.ingestion.loader import Loader
from src.utils.config import PipelineConfig
from src.utils.data_generator import generate_dataset


@pytest.fixture(scope="module")
def raw(tmp_path_factory):
    root = tmp_path_factory.mktemp("raw")
    for name, df in generate_dataset(n_days=12, daily_volume=600, seed=5, end=pd.Timestamp("2026-06-01")).items():
        df.to_parquet(root / f"{name}.parquet", index=False)
    return root


@pytest.fixture
def config(raw, tmp_path):
    return PipelineConfig(raw_dir=str(raw), lake_root=str(tmp_path / "lake"))


def lake(config, entity):
    files = glob.glob(os.path.join(config.lake_root, entity, "dt=*", "*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def audit(config, entity):
    files = glob.glob(os.path.join(config.lake_root, "_audit", entity, "*.json"))
    return pd.DataFrame([json.loads(open(f).read()) for f in files])


def test_impressions_partitioned_by_event_date_and_deduplicated(raw, config):
    summary = Loader("impressions", config).run()
    source = pd.read_parquet(raw / "impressions.parquet")

    landed = lake(config, "impressions")
    assert landed["impression_id"].is_unique
    assert len(landed) == source["impression_id"].nunique()
    assert summary["partitions"] == source["timestamp"].dt.date.nunique()
    assert audit(config, "impressions")["duplicates_dropped"].sum() == source["impression_id"].duplicated().sum()


def test_rerun_is_idempotent(config):
    Loader("clicks", config).run()
    first = len(lake(config, "clicks"))
    Loader("clicks", config).run()
    assert len(lake(config, "clicks")) == first


def test_single_partition_load(raw, config):
    day = str(pd.read_parquet(raw / "impressions.parquet")["timestamp"].dt.date.iloc[-1])
    Loader("impressions", config).run(partition_date=day)
    partitions = os.listdir(os.path.join(config.lake_root, "impressions"))
    assert partitions == [f"dt={day}"]


def test_conversions_partitioned_by_arrival_date(config):
    Loader("conversions", config).run()
    for f in glob.glob(os.path.join(config.lake_root, "conversions", "dt=*", "*.parquet")):
        day = os.path.basename(os.path.dirname(f))[3:]
        assert (pd.read_parquet(f)["received_at"].dt.date.astype(str) == day).all()
    assert audit(config, "conversions")["late_arrivals"].sum() >= 0


def test_missing_column_is_rejected(tmp_path, config):
    bad = tmp_path / "bad.parquet"
    pd.DataFrame({"impression_id": ["a"]}).to_parquet(bad)
    with pytest.raises(ValueError, match="missing required columns"):
        Loader("impressions", config).run(source_path=str(bad))
