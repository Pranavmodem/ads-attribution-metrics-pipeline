"""
config.py
Centralized pipeline configuration loaded from environment variables.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass
class PipelineConfig:
    """Pipeline configuration — all values from environment."""
    gcp_project_id: str
    gcs_bucket: str
    bq_dataset_raw: str = "ads_raw"
    bq_dataset_staging: str = "ads_staging"
    bq_dataset_marts: str = "ads_marts"
    gcs_raw_prefix: str = "raw/"
    gcs_processed_prefix: str = "processed/"
    attribution_window_days: int = 30
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        load_dotenv()
        return cls(
            gcp_project_id=os.environ["GCP_PROJECT_ID"],
            gcs_bucket=os.environ["GCS_BUCKET"],
            bq_dataset_raw=os.getenv("BQ_DATASET_RAW", "ads_raw"),
            bq_dataset_staging=os.getenv("BQ_DATASET_STAGING", "ads_staging"),
            bq_dataset_marts=os.getenv("BQ_DATASET_MARTS", "ads_marts"),
            gcs_raw_prefix=os.getenv("GCS_RAW_PREFIX", "raw/"),
            gcs_processed_prefix=os.getenv("GCS_PROCESSED_PREFIX", "processed/"),
            attribution_window_days=int(os.getenv("ATTRIBUTION_WINDOW_DAYS", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
