"""
impression_loader.py
Loads raw ad impression events from source files into GCS raw zone and BigQuery staging.

Handles: JSON, CSV, and Parquet formats with schema validation.
Supports both full-refresh and incremental loading patterns.
"""
import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd
from google.cloud import bigquery, storage

from src.utils.config import PipelineConfig
from src.utils.quality_checks import check_completeness

logger = logging.getLogger(__name__)


class ImpressionLoader:
    """Ingests ad impression events into the raw zone.

    Impression events contain: timestamp, placement_id, creative_id,
    campaign_id, user_segment, device_type, geo, and bid metadata.
    """

    REQUIRED_COLUMNS = [
        "impression_id",
        "timestamp",
        "campaign_id",
        "placement_id",
        "creative_id",
        "user_segment_id",
        "device_type",
        "geo_country",
        "bid_price_usd",
    ]

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig.from_env()
        self.bq_client = bigquery.Client(project=self.config.gcp_project_id)
        self.gcs_client = storage.Client(project=self.config.gcp_project_id)
        self.bucket = self.gcs_client.bucket(self.config.gcs_bucket)

    def extract(self, source_path: str, file_format: str = "parquet") -> pd.DataFrame:
        """Extract impression records from source files.

        Args:
            source_path: Local path or GCS URI to source data.
            file_format: One of 'parquet', 'csv', 'json'.

        Returns:
            DataFrame of raw impression events.
        """
        logger.info(f"Extracting impressions from {source_path} ({file_format})")

        readers = {
            "parquet": pd.read_parquet,
            "csv": pd.read_csv,
            "json": lambda p: pd.read_json(p, lines=True),
        }

        if file_format not in readers:
            raise ValueError(f"Unsupported format: {file_format}. Use: {list(readers.keys())}")

        df = readers[file_format](source_path)
        logger.info(f"Extracted {len(df):,} impression records")
        return df

    def validate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate schema and apply basic quality checks.

        Drops records with null impression_id (non-negotiable).
        Logs warnings for other quality issues without dropping rows.
        """
        # Schema check
        missing_cols = set(self.REQUIRED_COLUMNS) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        initial_count = len(df)

        # Drop records with null primary key
        df = df.dropna(subset=["impression_id"])

        # Deduplicate on impression_id (keep first occurrence)
        df = df.drop_duplicates(subset=["impression_id"], keep="first")

        dropped = initial_count - len(df)
        if dropped > 0:
            logger.warning(f"Dropped {dropped:,} records (null/duplicate impression_id)")

        # Type casting
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["bid_price_usd"] = pd.to_numeric(df["bid_price_usd"], errors="coerce").fillna(0.0)

        logger.info(f"Validation passed: {len(df):,} records retained")
        return df

    def load_to_gcs(self, df: pd.DataFrame, partition_date: str) -> str:
        """Write validated dataframe as Parquet to GCS raw zone.

        Partitioned by date for efficient downstream querying.

        Args:
            df: Validated impression dataframe.
            partition_date: Date string (YYYY-MM-DD) for partition path.

        Returns:
            GCS URI of the written file.
        """
        blob_path = f"{self.config.gcs_raw_prefix}impressions/dt={partition_date}/impressions.parquet"
        local_tmp = f"/tmp/impressions_{partition_date}.parquet"

        df.to_parquet(local_tmp, index=False, engine="pyarrow")

        blob = self.bucket.blob(blob_path)
        blob.upload_from_filename(local_tmp)

        gcs_uri = f"gs://{self.config.gcs_bucket}/{blob_path}"
        logger.info(f"Loaded {len(df):,} impressions to {gcs_uri}")

        # Cleanup
        os.remove(local_tmp)
        return gcs_uri

    def load_to_bigquery(self, gcs_uri: str, partition_date: str) -> None:
        """Load Parquet from GCS into BigQuery raw table.

        Uses WRITE_TRUNCATE for the specific partition to ensure idempotency.
        """
        table_id = f"{self.config.gcp_project_id}.{self.config.bq_dataset_raw}.impressions${partition_date.replace('-', '')}"

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            time_partitioning=bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp",
            ),
        )

        load_job = self.bq_client.load_table_from_uri(
            gcs_uri, table_id, job_config=job_config
        )
        load_job.result()  # Wait for completion

        logger.info(f"Loaded to BigQuery: {table_id}")

    def run(self, source_path: str, partition_date: str, file_format: str = "parquet") -> dict:
        """Execute full ingestion: extract → validate → load (GCS + BQ).

        Returns:
            Summary dict with record counts and destination URIs.
        """
        logger.info(f"Starting impression ingestion for {partition_date}")

        df = self.extract(source_path, file_format)
        df = self.validate(df)
        gcs_uri = self.load_to_gcs(df, partition_date)
        self.load_to_bigquery(gcs_uri, partition_date)

        summary = {
            "partition_date": partition_date,
            "records_loaded": len(df),
            "gcs_uri": gcs_uri,
            "status": "success",
        }

        logger.info(f"Impression ingestion complete: {summary}")
        return summary


if __name__ == "__main__":
    import sys
    from src.utils.logging_config import setup_logging

    setup_logging()

    source = sys.argv[1] if len(sys.argv) > 1 else "data/raw/impressions.parquet"
    date = sys.argv[2] if len(sys.argv) > 2 else datetime.utcnow().strftime("%Y-%m-%d")

    loader = ImpressionLoader()
    result = loader.run(source, date)
    print(f"Done: {result}")
