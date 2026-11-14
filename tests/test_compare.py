"""
test_compare.py
All seven models run on the same data and each hands out exactly one conversion's worth of credit.
"""
import pandas as pd
import pytest

from src.metrics.compare import MODELS, channel_credits, touchpoint_credits
from src.utils.data_generator import generate_dataset


@pytest.fixture(scope="module")
def frames():
    data = generate_dataset(n_days=30, daily_volume=1500, seed=9, end=pd.Timestamp("2026-06-01"))
    return data["impressions"].drop_duplicates("impression_id"), data["conversions"].drop_duplicates("conversion_id")


def test_touchpoint_credits_sum_to_one_per_conversion(frames):
    tp = touchpoint_credits(*frames)
    totals = tp.groupby(["model", "conversion_id"])["credit"].sum()
    assert totals.to_numpy() == pytest.approx(1.0)
    assert (tp["impression_ts"] <= tp["conversion_ts"]).all()


def test_channel_credits_cover_every_model(frames):
    credits = channel_credits(*frames)
    assert set(credits["model"]) == set(MODELS)
    assert credits.groupby("model")["credit"].sum().to_numpy() == pytest.approx(1.0)


def test_last_touch_overcredits_intent_channels(frames):
    credits = channel_credits(*frames).pivot(index="channel", columns="model", values="credit")
    assert credits.loc["Paid Search", "last_touch"] > credits.loc["Paid Search", "first_touch"]
    assert credits.loc["Display", "first_touch"] > credits.loc["Display", "last_touch"]
