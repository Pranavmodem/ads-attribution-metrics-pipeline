"""
test_advanced_attribution.py
Markov, Shapley, position-based, and journey building.
"""
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from src.metrics.advanced_attribution import (
    MarkovAttribution,
    PositionBasedAttribution,
    ShapleyAttribution,
    build_journeys,
    exposure_shapley,
)


class TestMarkov:
    def test_conversion_probability_counts_non_converters(self):
        m = MarkovAttribution().fit([["A"]] * 10, [["A"]] * 30)
        assert m.conversion_probability == pytest.approx(0.25)

    def test_removal_effects_match_hand_calculation(self):
        # start->A 30, start->B 10, A->B 10, A->null 20, B->conv 20: P(conv) = 0.5.
        # Removing A leaves 0.25 (effect 0.5); removing B leaves 0 (effect 1).
        m = MarkovAttribution().fit([["A", "B"]] * 10 + [["B"]] * 10, [["A"]] * 20)
        credit = m.get_attribution()
        assert credit["A"] == pytest.approx(1 / 3)
        assert credit["B"] == pytest.approx(2 / 3)

    def test_channel_seen_only_by_non_converters_gets_nothing(self):
        credit = MarkovAttribution().fit([["A"]] * 5, [["C"]] * 50).get_attribution()
        assert set(credit) == {"A"}

    def test_second_order_shares_sum_to_one(self):
        conv = [["A", "B", "C"]] * 5 + [["B", "C"]] * 5
        credit = MarkovAttribution(order=2).fit(conv, [["A", "B"]] * 10).get_attribution()
        assert sum(credit.values()) == pytest.approx(1.0)
        assert credit["C"] > credit["A"]


class TestExposureShapley:
    def test_efficiency_with_interactions(self):
        rng = np.random.default_rng(0)
        counts = rng.integers(0, 3, size=(200, 4)).astype(float)

        def logit(c):
            return -2 + c @ np.array([0.5, 0.3, -0.2, 0.8]) + 0.4 * (c[:, 0] > 0) * (c[:, 3] > 0)

        sigmoid = lambda z: 1 / (1 + np.exp(-z))  # noqa: E731
        expected = (sigmoid(logit(counts)) - sigmoid(logit(np.zeros_like(counts)))).sum()
        assert exposure_shapley(counts, logit).sum() == pytest.approx(expected)

    def test_symmetric_channels_get_equal_credit(self):
        counts = np.array([[1, 1, 0], [1, 1, 1], [0, 1, 1], [1, 0, 1]], dtype=float)
        credit = exposure_shapley(counts, lambda c: -1 + (c > 0) @ np.array([0.7, 0.7, 0.7]))
        exposures = (counts > 0).sum(axis=0)
        # Equal effects: credit per exposure is the same for every channel.
        assert np.allclose(credit / exposures, (credit / exposures)[0], rtol=0.2)


class TestShapleyAttribution:
    def test_recovers_effect_ordering(self):
        rng = np.random.default_rng(7)
        n = 20_000
        exposed = rng.random((n, 3)) < 0.5
        p = 1 / (1 + np.exp(-(-3 + exposed @ np.array([1.5, 0.6, 0.0]))))
        converted = rng.random(n) < p
        journeys = [[ch for ch, on in zip("ABC", row) if on] for row in exposed]
        conv = [j for j, c in zip(journeys, converted) if c and j]  # users never reached have no journey
        non = [j for j, c in zip(journeys, converted) if not c and j]

        credit = ShapleyAttribution().fit(conv, non).get_attribution()
        assert credit["A"] > credit["B"] > credit["C"]
        assert credit["C"] < 0.05
        assert sum(credit.values()) == pytest.approx(1.0)

    def test_too_many_channels_rejected(self):
        journey = [f"ch{i}" for i in range(13)]
        with pytest.raises(ValueError, match="too many"):
            ShapleyAttribution().fit([journey], [])


class TestPositionBased:
    def test_u_shape(self):
        credit = PositionBasedAttribution.attribute_journey(["A", "B", "C", "D"])
        assert credit == pytest.approx({"A": 0.4, "B": 0.1, "C": 0.1, "D": 0.4})

    def test_repeated_channel_accumulates(self):
        credit = PositionBasedAttribution.attribute_journey(["A", "B", "A"])
        assert credit == pytest.approx({"A": 0.8, "B": 0.2})


class TestBuildJourneys:
    def test_both_sides_use_the_lookback_window(self):
        t0 = datetime(2026, 1, 31)
        impressions = pd.DataFrame([
            # converting user: one impression too old, two inside the window
            {"user_id": "u1", "timestamp": t0 - timedelta(days=45), "channel": "Display"},
            {"user_id": "u1", "timestamp": t0 - timedelta(days=5), "channel": "Video"},
            {"user_id": "u1", "timestamp": t0 - timedelta(days=1), "channel": "Paid Search"},
            # non-converting user: window anchors on their last impression
            {"user_id": "u2", "timestamp": t0 - timedelta(days=50), "channel": "Display"},
            {"user_id": "u2", "timestamp": t0 - timedelta(days=2), "channel": "Social"},
            {"user_id": "u2", "timestamp": t0, "channel": "Email"},
        ])
        conversions = pd.DataFrame([{"user_id": "u1", "timestamp": t0}])

        converting, non_converting = build_journeys(impressions, conversions, attribution_window_days=30)
        assert converting == [["Video", "Paid Search"]]
        assert non_converting == [["Social", "Email"]]

    def test_impressions_after_conversion_are_ignored(self):
        t0 = datetime(2026, 1, 31)
        impressions = pd.DataFrame([
            {"user_id": "u1", "timestamp": t0 - timedelta(days=1), "channel": "Video"},
            {"user_id": "u1", "timestamp": t0 + timedelta(days=1), "channel": "Email"},
        ])
        converting, _ = build_journeys(impressions, pd.DataFrame([{"user_id": "u1", "timestamp": t0}]))
        assert converting == [["Video"]]
