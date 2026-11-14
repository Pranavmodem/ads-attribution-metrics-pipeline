"""
test_data_generator.py
The synthetic data has to behave like the real thing, or the model comparison means nothing.
"""
import pandas as pd
import pytest

from src.metrics.advanced_attribution import build_journeys
from src.utils.data_generator import CHANNEL_NAMES, generate_dataset, true_channel_credit


@pytest.fixture(scope="module")
def data():
    return generate_dataset(n_days=45, daily_volume=1500, seed=3, end=pd.Timestamp("2026-06-01"))


def test_same_seed_same_data():
    a = generate_dataset(n_days=10, daily_volume=300, seed=11, end=pd.Timestamp("2026-06-01"))
    b = generate_dataset(n_days=10, daily_volume=300, seed=11, end=pd.Timestamp("2026-06-01"))
    for name in a:
        pd.testing.assert_frame_equal(a[name], b[name])


def test_every_channel_has_campaigns_and_impressions(data):
    assert set(data["campaigns"]["channel"]) == set(CHANNEL_NAMES)
    assert set(data["impressions"]["channel"]) == set(CHANNEL_NAMES)


def test_journeys_are_multi_touch(data):
    imps = data["impressions"].drop_duplicates("impression_id")
    conv = data["conversions"].drop_duplicates("conversion_id")
    converting, _ = build_journeys(imps, conv)
    multi = sum(len(j) > 1 for j in converting) / len(converting)
    assert multi > 0.8


def test_funnel_order(data):
    """Awareness channels come early in a journey, intent channels late."""
    imps = data["impressions"].drop_duplicates("impression_id").sort_values(["user_id", "timestamp"])
    imps["pos"] = imps.groupby("user_id").cumcount() / imps.groupby("user_id")["user_id"].transform("size")
    pos = imps.groupby("channel")["pos"].mean()
    assert pos["Display"] < pos["Social"] < pos["Paid Search"]


def test_business_metrics_are_plausible(data):
    imps = data["impressions"].drop_duplicates("impression_id")
    conv = data["conversions"].drop_duplicates("conversion_id")
    spend = imps["bid_price_usd"].sum() / 1000
    ctr = len(data["clicks"]) / len(imps)
    reach_rate = conv["user_id"].nunique() / imps["user_id"].nunique()
    assert 0.005 < ctr < 0.05
    assert 0.01 < reach_rate < 0.10
    assert 1.5 < conv["revenue_usd"].sum() / spend < 10


def test_clicks_and_conversions_follow_impressions(data):
    imps = data["impressions"].drop_duplicates("impression_id").set_index("impression_id")
    clicks = data["clicks"]
    assert (clicks["timestamp"] > imps.loc[clicks["impression_id"], "timestamp"].to_numpy()).all()

    first_seen = imps.groupby("user_id")["timestamp"].min()
    conv = data["conversions"]
    assert (conv["timestamp"] > first_seen.loc[conv["user_id"]].to_numpy()).all()


def test_planted_defects(data):
    imps, conv = data["impressions"], data["conversions"]
    assert imps["impression_id"].duplicated().sum() > 0
    assert conv["conversion_id"].duplicated().sum() > 0
    assert ((conv["received_at"] - conv["timestamp"]) > pd.Timedelta(hours=24)).sum() > 0
    # Nothing arrives after the export was taken.
    assert (conv["received_at"] < pd.Timestamp("2026-06-01")).all()


def test_ground_truth(data):
    truth = true_channel_credit(data["impressions"]).set_index("channel")["credit"]
    assert truth.sum() == pytest.approx(1.0)
    assert (truth > 0).all()
    assert truth["Video"] > truth["Native"]
    assert truth["Display"] > truth["Affiliate"]
