"""Each channel's true share of incremental conversions, from the generator's own coefficients.

Only meaningful on synthetic data; disabled when var synthetic_ground_truth is false.
"""


def model(dbt, session):
    dbt.config(materialized="table")
    import os
    import sys

    sys.path.insert(0, os.getcwd())
    from src.utils.data_generator import true_channel_credit

    impressions = dbt.ref("stg_impressions").df()
    return true_channel_credit(impressions)
