"""
config.py
Pipeline settings, read from environment variables with local defaults.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineConfig:
    raw_dir: str = "data/raw"                    # where upstream exports land
    lake_root: str = "data/lake"                 # partitioned Parquet; a gs:// URI works with gcsfs
    warehouse_path: str = "data/warehouse.duckdb"
    attribution_window_days: int = 30
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        return cls(
            raw_dir=os.getenv("RAW_DIR", cls.raw_dir),
            lake_root=os.getenv("LAKE_ROOT", cls.lake_root),
            warehouse_path=os.getenv("WAREHOUSE_PATH", cls.warehouse_path),
            attribution_window_days=int(os.getenv("ATTRIBUTION_WINDOW_DAYS", cls.attribution_window_days)),
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
        )
