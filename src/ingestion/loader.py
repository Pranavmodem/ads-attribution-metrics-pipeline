"""
loader.py
Lands upstream exports in the lake as date-partitioned Parquet.

    <raw_dir>/<entity>.parquet  ->  <lake_root>/<entity>/dt=YYYY-MM-DD/part-0.parquet
                                    <lake_root>/_audit/<entity>/dt=YYYY-MM-DD.json

Each partition is overwritten whole, so re-running a date is safe. Impressions
and clicks are partitioned by event date. Conversions are partitioned by the
date they arrived (received_at), the usual way to absorb late events: a
conversion that happened Monday but arrived Thursday lands in Thursday's
partition, and the dbt staging model deduplicates across partitions.
Campaigns are a dimension, so each load writes a full snapshot.

lake_root can be a gs:// URI (install gcsfs); nothing else changes.
"""
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional, Tuple

import pandas as pd

from src.utils.config import PipelineConfig

logger = logging.getLogger(__name__)

LATE_ARRIVAL = pd.Timedelta(hours=24)


@dataclass(frozen=True)
class EntitySpec:
    key: str
    required: Tuple[str, ...]
    partition_by: Optional[str] = None  # None = dimension snapshot partitioned by load date
    timestamps: Tuple[str, ...] = ()
    numeric: Tuple[str, ...] = ()


ENTITIES = {
    "impressions": EntitySpec(
        key="impression_id",
        required=("impression_id", "timestamp", "user_id", "campaign_id", "channel", "bid_price_usd"),
        partition_by="timestamp",
        timestamps=("timestamp",),
        numeric=("bid_price_usd",),
    ),
    "clicks": EntitySpec(
        key="click_id",
        required=("click_id", "impression_id", "timestamp", "user_id", "campaign_id", "channel"),
        partition_by="timestamp",
        timestamps=("timestamp",),
    ),
    "conversions": EntitySpec(
        key="conversion_id",
        required=("conversion_id", "timestamp", "received_at", "user_id", "conversion_type", "revenue_usd"),
        partition_by="received_at",
        timestamps=("timestamp", "received_at"),
        numeric=("revenue_usd",),
    ),
    "campaigns": EntitySpec(
        key="campaign_id",
        required=("campaign_id", "campaign_name", "advertiser_name", "channel"),
    ),
}


def _join(*parts: str) -> str:
    return "/".join(p.rstrip("/") for p in parts)


class Loader:
    """Extract one entity's export, validate it, and write lake partitions."""

    def __init__(self, entity: str, config: Optional[PipelineConfig] = None):
        if entity not in ENTITIES:
            raise ValueError(f"Unknown entity {entity!r}. Use one of {list(ENTITIES)}")
        self.entity = entity
        self.spec = ENTITIES[entity]
        self.config = config or PipelineConfig.from_env()

    def extract(self, source_path: Optional[str] = None) -> pd.DataFrame:
        path = source_path or os.path.join(self.config.raw_dir, f"{self.entity}.parquet")
        readers = {".parquet": pd.read_parquet, ".csv": pd.read_csv,
                   ".json": lambda p: pd.read_json(p, lines=True)}
        ext = os.path.splitext(path)[1]
        if ext not in readers:
            raise ValueError(f"Unsupported format {ext!r}; use {list(readers)}")
        df = readers[ext](path)
        logger.info(f"Extracted {len(df):,} {self.entity} rows from {path}")
        return df

    def validate(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Enforce the schema, cast types, and set aside null keys and duplicate keys.

        Duplicates keep the earliest copy (by received_at when the entity has it).

        Returns:
            (clean rows, rejected rows with a `reject_reason` column)
        """
        missing = set(self.spec.required) - set(df.columns)
        if missing:
            raise ValueError(f"{self.entity}: missing required columns {sorted(missing)}")

        df = df.copy()
        for col in self.spec.timestamps:
            df[col] = pd.to_datetime(df[col], utc=True).dt.tz_localize(None).astype("datetime64[us]")
        for col in self.spec.numeric:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        order = "received_at" if "received_at" in df.columns else self.spec.partition_by
        if order:
            df = df.sort_values(order, kind="mergesort")
        null_key = df[self.spec.key].isna()
        duplicate = df.duplicated(subset=[self.spec.key], keep="first") & ~null_key
        rejected = df[null_key | duplicate].assign(
            reject_reason=lambda d: d[self.spec.key].isna().map({True: "null_key", False: "duplicate"})
        )
        clean = df[~(null_key | duplicate)].reset_index(drop=True)
        if len(rejected):
            logger.warning(f"{self.entity}: set aside {len(rejected):,} rows "
                           f"({rejected['reject_reason'].value_counts().to_dict()})")
        return clean, rejected

    def write(self, df: pd.DataFrame, rejected: pd.DataFrame, partition_date: Optional[str]) -> list:
        """Overwrite each touched partition and its audit record."""
        if self.spec.partition_by:
            dt = df[self.spec.partition_by].dt.date.astype(str)
            rejected_dt = rejected[self.spec.partition_by].dt.date.astype(str)
            if partition_date:
                df, dt = df[dt == partition_date], dt[dt == partition_date]
                rejected = rejected[rejected_dt == partition_date]
                rejected_dt = rejected_dt[rejected_dt == partition_date]
            partitions = sorted(dt.unique())
        else:
            snapshot = partition_date or date.today().isoformat()
            dt = pd.Series(snapshot, index=df.index)
            rejected_dt = pd.Series(snapshot, index=rejected.index)
            partitions = [snapshot]

        loaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for day in partitions:
            part = df[dt == day]
            directory = _join(self.config.lake_root, self.entity, f"dt={day}")
            if "://" not in directory:
                os.makedirs(directory, exist_ok=True)
            part.to_parquet(_join(directory, "part-0.parquet"), index=False)
            self._write_audit(day, part, rejected[rejected_dt == day], loaded_at)
        logger.info(f"{self.entity}: wrote {len(partitions)} partition(s), {len(df):,} rows")
        return partitions

    def _write_audit(self, day: str, part: pd.DataFrame, rejected: pd.DataFrame, loaded_at: str) -> None:
        directory = _join(self.config.lake_root, "_audit", self.entity)
        if "://" not in directory:
            os.makedirs(directory, exist_ok=True)
        reasons = rejected["reject_reason"].value_counts() if len(rejected) else pd.Series(dtype=int)
        record = {
            "entity": self.entity,
            "dt": day,
            "rows_loaded": len(part),
            "duplicates_dropped": int(reasons.get("duplicate", 0)),
            "null_keys_dropped": int(reasons.get("null_key", 0)),
            "late_arrivals": 0,
            "loaded_at": loaded_at,
        }
        if self.entity == "conversions":
            record["late_arrivals"] = int(((part["received_at"] - part["timestamp"]) > LATE_ARRIVAL).sum())
        pd.DataFrame([record]).to_json(_join(directory, f"dt={day}.json"), orient="records", lines=True)

    def run(self, partition_date: Optional[str] = None, source_path: Optional[str] = None) -> dict:
        raw = self.extract(source_path)
        df, rejected = self.validate(raw)
        partitions = self.write(df, rejected, partition_date)
        return {
            "entity": self.entity,
            "partition_date": partition_date,
            "partitions": len(partitions),
            "rows_in": len(raw),
            "rows_rejected": len(rejected),
        }
