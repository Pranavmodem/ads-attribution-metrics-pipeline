"""Channel credit shares from all seven models. Each model's shares sum to 1."""


def model(dbt, session):
    dbt.config(materialized="table")
    import os
    import sys

    sys.path.insert(0, os.getcwd())
    from src.metrics.compare import channel_credits

    window = int(dbt.config.get("attribution_window_days"))
    impressions = dbt.ref("stg_impressions").df().rename(columns={"impression_ts": "timestamp"})
    conversions = dbt.ref("stg_conversions").df().rename(columns={"conversion_ts": "timestamp"})
    touchpoints = dbt.ref("attribution_touchpoints").df()
    return channel_credits(impressions, conversions, window_days=window, touchpoints=touchpoints)
