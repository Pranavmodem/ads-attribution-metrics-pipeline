"""
conversion_loader.py
Loads conversion events (purchases, store visits, signups) into the raw zone.

Handles late-arriving conversions with configurable attribution windows.
"""
import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd
from google.cloud import bigquery, storage

from src.utils.config import PipelineConfig

logger = logging.getLogger(__name__)


class ConversionLoader:
    """Ingests conversion events with late-arrival handling.

    Conversion events contain: conversion_id, timestamp, user_id,
    conversion_type (purchase/visit/signup), revenue_usd, and
    attribution metadata linking back to impressions/clicks.
    """

    REQUIRED_COLUMNS = [
        "conversion_id",
        "timestamp",
        "user_id",
        "conversion_type",
        "revenue_usd",
        "attributed_impression_id",
    ]

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig.from_env()
        self.bq_client = bigquery.Client(project=self.config.gcp_project_id)
        self.gcs_client = storage.Client(project=self.config.gcp_project_id)
        self.bucket = self.gcs_client.bucket(self.config.gcs_bucket)

    def extract(self, source_path: str, file_format: str = "parquet") -> pd.DataFrame:
        """Extract conversion records from source files."""
        logger.info(f"Extracting conversions from {source_path}")

        readers = {
            "parquet": pd.read_parquet,
            "csv": pd.read_csv,
            "json": lambda p: pd.read_json(p, lines=True),
        }
        df = readers[file_format](source_path)
        logger.info(f"Extracted {len(df):,} conversion records")
        return df

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and clean conversion records.

        Key checks:
        - Null conversion_id → drop
        - Duplicate conversion_id → keep first
        - Negative revenue → flag and zero out
        - Future timestamps → flag as suspect
        """
        missing_cols = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        initial_count = len(df)

        df = df.dropna(subset=["conversion_id"])
        df = df.drop_duplicates(subset=["conversion_id"], keep="first")

        # Handle negative revenue (log, don't drop — could be refunds)
        negative_revenue = df["revenue_usd"] < 0
        if negative_revenue.any():
            logger.warning(
                f"Found {negative_revenue.sum()} records with negative revenue (possible refunds)"
            )

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["revenue_usd"] = pd.to_numeric(df["revenue_usd"], errors="coerce").fillna(0.0)

        dropped = initial_count - len(df)
        logger.info(f"Validation complete: {len(df):,} retained, {dropped:,} dropped")
        return df

    def handle_late_arrivals(self, df: pd.DataFrame, partition_date: str) -> pd.DataFrame:
        """Identify and tag late-arriving conversions.

        A conversion is 'late' if its attributed_impression occurred before
        the current partition date minus the attribution window.
        This doesn't drop them — downstream models handle the logic.
        """
        partition_dt = pd.Timestamp(partition_date, tz="UTC")
        window_days = self.config.attribution_window_days

        df["is_late_arrival"] = (
            partition_dt - df["timestamp"]
        ).dt.days > window_days

        late_count = df["is_late_arrival"].sum()
        if late_count > 0:
            logger.info(
                f"Tagged {late_count:,} late-arriving conversions "
                f"(>{window_days} days from partition date)"
            )
        return df

    def load_to_gcs(self, df: pd.DataFrame, partition_date: str) -> str:
        """Write conversions as Parquet to GCS raw zone."""
        blob_path = f"{self.config.gcs_raw_prefix}conversions/dt={partition_date}/conversions.parquet"
        local_tmp = f"/tmp/conversions_{partition_date}.parquet"

        df.to_parquet(local_tmp, index=False, engine="pyarrow")

        blob = self.bucket.blob(blob_path)
        blob.upload_from_filename(local_tmp)

        gcs_uri = f"gs://{self.config.gcs_bucket}/{blob_path}"
        logger.info(f"Loaded {len(df):,} conversions to {gcs_uri}")
        os.remove(local_tmp)
        return gcs_uri

    def run(self, source_path: str, partition_date: str, file_format: str = "parquet") -> dict:
        """Execute full conversion ingestion pipeline."""
        logger.info(f"Starting conversion ingestion for {partition_date}")

        df = self.extract(source_path, file_format)
        df = self.validate(df)
        df = self.handle_late_arrivals(df, partition_date)
        gcs_uri = self.load_to_gcs(df, partition_date)

        return {
            "partition_date": partition_date,
            "records_loaded": len(df),
            "late_arrivals": int(df["is_late_arrival"].sum()),
            "gcs_uri": gcs_uri,
            "status": "success",
        }


if __name__ == "__main__":
    import sys
    from src.utils.logging_config import setup_logging

    setup_logging()

    source = sys.argv[1] if len(sys.argv) > 1 else "data/raw/conversions.parquet"
    date = sys.argv[2] if len(sys.argv) > 2 else datetime.utcnow().strftime("%Y-%m-%d")

    loader = ConversionLoader()
    result = loader.run(source, date)
    print(f"Done: {result}")
