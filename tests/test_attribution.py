"""
test_attribution.py
Unit tests for the attribution engine.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.metrics.attribution import AttributionEngine


@pytest.fixture
def sample_impressions():
    """Three impressions for the same user, spread over 7 days."""
    base_time = datetime(2026, 1, 15, 10, 0, 0)
    return pd.DataFrame([
        {
            "impression_id": "imp_001",
            "user_id": "user_001",
            "timestamp": base_time - timedelta(days=7),
            "campaign_id": "camp_001",
        },
        {
            "impression_id": "imp_002",
            "user_id": "user_001",
            "timestamp": base_time - timedelta(days=3),
            "campaign_id": "camp_001",
        },
        {
            "impression_id": "imp_003",
            "user_id": "user_001",
            "timestamp": base_time - timedelta(days=1),
            "campaign_id": "camp_002",
        },
    ])


@pytest.fixture
def sample_conversion():
    """Single conversion for user_001."""
    return pd.DataFrame([
        {
            "conversion_id": "conv_001",
            "user_id": "user_001",
            "timestamp": datetime(2026, 1, 15, 14, 0, 0),
            "revenue_usd": 100.0,
        }
    ])


class TestLastTouchAttribution:
    def test_credits_last_impression(self, sample_impressions, sample_conversion):
        engine = AttributionEngine(model="last_touch")
        result = engine.attribute(sample_impressions, sample_conversion)

        assert len(result) == 1
        assert result.iloc[0]["impression_id"] == "imp_003"
        assert result.iloc[0]["credit"] == 1.0
        assert result.iloc[0]["revenue_attributed"] == 100.0

    def test_no_impressions_no_attribution(self, sample_conversion):
        engine = AttributionEngine(model="last_touch")
        empty_impressions = pd.DataFrame(
            columns=["impression_id", "user_id", "timestamp", "campaign_id"]
        )
        result = engine.attribute(empty_impressions, sample_conversion)
        assert len(result) == 0


class TestFirstTouchAttribution:
    def test_credits_first_impression(self, sample_impressions, sample_conversion):
        engine = AttributionEngine(model="first_touch")
        result = engine.attribute(sample_impressions, sample_conversion)

        assert len(result) == 1
        assert result.iloc[0]["impression_id"] == "imp_001"
        assert result.iloc[0]["credit"] == 1.0


class TestLinearAttribution:
    def test_equal_credit_distribution(self, sample_impressions, sample_conversion):
        engine = AttributionEngine(model="linear")
        result = engine.attribute(sample_impressions, sample_conversion)

        assert len(result) == 3
        expected_credit = 1.0 / 3
        for _, row in result.iterrows():
            assert abs(row["credit"] - expected_credit) < 0.01

    def test_revenue_sums_to_total(self, sample_impressions, sample_conversion):
        engine = AttributionEngine(model="linear")
        result = engine.attribute(sample_impressions, sample_conversion)

        total_attributed = result["revenue_attributed"].sum()
        assert abs(total_attributed - 100.0) < 0.01


class TestTimeDecayAttribution:
    def test_recent_gets_more_credit(self, sample_impressions, sample_conversion):
        engine = AttributionEngine(model="time_decay", decay_half_life_days=7.0)
        result = engine.attribute(sample_impressions, sample_conversion)

        assert len(result) == 3

        # Most recent impression should get highest credit
        credits = result.set_index("impression_id")["credit"]
        assert credits["imp_003"] > credits["imp_002"] > credits["imp_001"]

    def test_credits_sum_to_one(self, sample_impressions, sample_conversion):
        engine = AttributionEngine(model="time_decay")
        result = engine.attribute(sample_impressions, sample_conversion)

        total_credit = result["credit"].sum()
        assert abs(total_credit - 1.0) < 0.001


class TestAttributionWindow:
    def test_impressions_outside_window_excluded(self):
        """Impressions older than the attribution window should not receive credit."""
        base_time = datetime(2026, 1, 15, 10, 0, 0)

        impressions = pd.DataFrame([
            {
                "impression_id": "imp_old",
                "user_id": "user_001",
                "timestamp": base_time - timedelta(days=45),  # Outside 30-day window
                "campaign_id": "camp_001",
            },
            {
                "impression_id": "imp_recent",
                "user_id": "user_001",
                "timestamp": base_time - timedelta(days=2),
                "campaign_id": "camp_001",
            },
        ])

        conversions = pd.DataFrame([
            {
                "conversion_id": "conv_001",
                "user_id": "user_001",
                "timestamp": base_time,
                "revenue_usd": 50.0,
            }
        ])

        engine = AttributionEngine(model="last_touch", attribution_window_days=30)
        result = engine.attribute(impressions, conversions)

        assert len(result) == 1
        assert result.iloc[0]["impression_id"] == "imp_recent"
