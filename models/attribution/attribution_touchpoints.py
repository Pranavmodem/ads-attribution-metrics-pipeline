"""Impression-level credit from the four heuristic models (last touch, first touch, linear, time decay)."""


def model(dbt, session):
    dbt.config(materialized="table")
    import os
    import sys

    sys.path.insert(0, os.getcwd())
    from src.metrics.compare import touchpoint_credits

    window = int(dbt.config.get("attribution_window_days"))
    impressions = dbt.ref("stg_impressions").df().rename(columns={"impression_ts": "timestamp"})
    conversions = dbt.ref("stg_conversions").df().rename(columns={"conversion_ts": "timestamp"})
    return touchpoint_credits(impressions, conversions, window_days=window)
