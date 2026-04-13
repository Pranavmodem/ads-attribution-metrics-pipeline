"""
advanced_attribution.py
Data-driven attribution models using Markov chains and Shapley values.

These go beyond heuristic models (last-touch, linear, etc.) by using
probabilistic and game-theoretic methods to fairly allocate conversion
credit across marketing channels.

References:
- ChannelAttribution (Markov): https://github.com/DavideAltomare/ChannelAttribution
- MTA (Shapley): https://github.com/eeghor/mta
"""
import logging
from itertools import combinations
from math import factorial
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def build_journeys(
    impressions: pd.DataFrame,
    conversions: pd.DataFrame,
    channel_col: str = "channel",
    attribution_window_days: int = 30,
) -> Tuple[List[List[str]], int]:
    """Build user journeys from impression and conversion data.

    Returns:
        Tuple of (converting_journeys, total_non_converting_users).
        Each journey is a list of channel names in chronological order.
    """
    impressions = impressions.copy()
    conversions = conversions.copy()
    impressions["timestamp"] = pd.to_datetime(impressions["timestamp"])
    conversions["timestamp"] = pd.to_datetime(conversions["timestamp"])

    converted_users = set(conversions["user_id"].unique())
    window = pd.Timedelta(days=attribution_window_days)

    converting_journeys = []
    imp_grouped = impressions.sort_values("timestamp").groupby("user_id")
    conv_grouped = conversions.groupby("user_id")
    for user_id in converted_users:
        if user_id not in imp_grouped.groups:
            continue
        user_imps = imp_grouped.get_group(user_id)
        first_conv_time = conv_grouped.get_group(user_id)["timestamp"].min()
        relevant_imps = user_imps[
            (user_imps["timestamp"] <= first_conv_time)
            & (user_imps["timestamp"] >= first_conv_time - window)
        ]
        if relevant_imps.empty:
            continue
        journey = relevant_imps[channel_col].tolist()
        converting_journeys.append(journey)

    all_users = set(impressions["user_id"].unique())
    non_converting_count = len(all_users - converted_users)

    logger.info(
        f"Built {len(converting_journeys)} converting journeys, "
        f"{non_converting_count} non-converting users"
    )
    return converting_journeys, non_converting_count


class MarkovAttribution:
    """Markov chain attribution model.

    Builds a transition probability matrix from user journey data and
    computes each channel's contribution via the removal effect:
    how much would total conversions drop if we removed a channel?

    Higher-order Markov chains capture sequence dependencies that
    heuristic models completely miss.
    """

    def __init__(self, order: int = 1):
        self.order = order
        self.transition_matrix: Dict[str, Dict[str, float]] = {}
        self.channels: List[str] = []
        self.removal_effects: Dict[str, float] = {}

    def fit(
        self,
        converting_journeys: List[List[str]],
        non_converting_count: int = 0,
    ) -> "MarkovAttribution":
        """Fit the Markov model on journey data.

        Args:
            converting_journeys: List of journeys (each a list of channels)
                that ended in conversion.
            non_converting_count: Number of users who saw ads but didn't convert.
        """
        self.channels = sorted(
            set(ch for journey in converting_journeys for ch in journey)
        )
        total_journeys = len(converting_journeys) + non_converting_count

        # Build transition counts: Start -> channels -> Conversion/Null
        transitions: Dict[str, Dict[str, int]] = {}

        for journey in converting_journeys:
            path = ["(start)"] + journey + ["(conversion)"]
            for i in range(len(path) - 1):
                src = path[i]
                dst = path[i + 1]
                transitions.setdefault(src, {})
                transitions[src][dst] = transitions[src].get(dst, 0) + 1

        # Add non-converting paths (start -> null or last channel -> null)
        if non_converting_count > 0:
            transitions.setdefault("(start)", {})
            transitions["(start)"]["(null)"] = (
                transitions["(start)"].get("(null)", 0) + non_converting_count
            )

        # Normalize to probabilities
        self.transition_matrix = {}
        for src, dsts in transitions.items():
            total = sum(dsts.values())
            self.transition_matrix[src] = {
                dst: count / total for dst, count in dsts.items()
            }

        # Compute removal effects
        base_conv_rate = self._simulate_conversion_rate(self.transition_matrix)
        self.removal_effects = {}

        for channel in self.channels:
            modified_matrix = self._remove_channel(self.transition_matrix, channel)
            modified_conv_rate = self._simulate_conversion_rate(modified_matrix)
            effect = (base_conv_rate - modified_conv_rate) / base_conv_rate if base_conv_rate > 0 else 0
            self.removal_effects[channel] = max(effect, 0)

        # Normalize removal effects to sum to 1
        total_effect = sum(self.removal_effects.values())
        if total_effect > 0:
            self.removal_effects = {
                ch: eff / total_effect for ch, eff in self.removal_effects.items()
            }

        logger.info(f"Markov model fitted: {len(self.channels)} channels, removal effects computed")
        return self

    def get_attribution(self) -> Dict[str, float]:
        """Return channel attribution weights (sum to 1.0)."""
        return dict(self.removal_effects)

    def get_transition_matrix_df(self) -> pd.DataFrame:
        """Return transition matrix as a DataFrame for visualization."""
        all_states = sorted(self.transition_matrix.keys())
        all_dests = sorted(
            set(d for dsts in self.transition_matrix.values() for d in dsts)
        )
        matrix = pd.DataFrame(0.0, index=all_states, columns=all_dests)
        for src, dsts in self.transition_matrix.items():
            for dst, prob in dsts.items():
                matrix.loc[src, dst] = prob
        return matrix

    def _simulate_conversion_rate(self, matrix: Dict[str, Dict[str, float]]) -> float:
        """Compute exact conversion probability using absorbing Markov chain math.

        Solves the system N = (I - Q)^{-1} where Q is the transient-state
        transition submatrix, then reads off absorption probabilities into
        the "(conversion)" state. This is exact and O(n^3) — no recursion.
        """
        if "(start)" not in matrix:
            return 0.0

        absorbing = {"(conversion)", "(null)"}
        all_states = set(matrix.keys())
        for dsts in matrix.values():
            all_states.update(dsts.keys())
        transient = sorted(s for s in all_states if s not in absorbing and s in matrix)

        if not transient:
            return matrix.get("(start)", {}).get("(conversion)", 0.0)

        state_idx = {s: i for i, s in enumerate(transient)}
        n = len(transient)

        # Build Q (transient-to-transient) and R (transient-to-absorbing)
        Q = np.zeros((n, n))
        conv_idx_col = 0  # column index for (conversion) in R
        R_conv = np.zeros(n)  # only need the (conversion) column of R

        for src in transient:
            i = state_idx[src]
            for dst, prob in matrix.get(src, {}).items():
                if dst in state_idx:
                    Q[i, state_idx[dst]] = prob
                elif dst == "(conversion)":
                    R_conv[i] = prob

        # Fundamental matrix N = (I - Q)^{-1}
        try:
            IQ = np.eye(n) - Q
            N = np.linalg.inv(IQ)
        except np.linalg.LinAlgError:
            return 0.0

        # Absorption probabilities B = N * R
        # We only need B[(start), (conversion)]
        if "(start)" not in state_idx:
            return 0.0

        start_i = state_idx["(start)"]
        return float(N[start_i] @ R_conv)

    def _remove_channel(
        self, matrix: Dict[str, Dict[str, float]], channel: str
    ) -> Dict[str, Dict[str, float]]:
        """Remove a channel: redirect all transitions to/from it to (null)."""
        modified = {}
        for src, dsts in matrix.items():
            if src == channel:
                continue
            new_dsts = {}
            for dst, prob in dsts.items():
                if dst == channel:
                    new_dsts["(null)"] = new_dsts.get("(null)", 0) + prob
                else:
                    new_dsts[dst] = prob
            modified[src] = new_dsts
        return modified


class ShapleyAttribution:
    """Shapley value attribution model.

    Uses cooperative game theory to fairly distribute conversion credit.
    For each channel, computes its marginal contribution across all possible
    coalitions (subsets) of channels.

    This is the mathematically fairest way to allocate credit — it satisfies
    efficiency, symmetry, linearity, and null-player axioms.
    """

    def __init__(self):
        self.channel_credits: Dict[str, float] = {}
        self.channels: List[str] = []
        self._coalition_values: Dict[frozenset, float] = {}

    def fit(
        self,
        converting_journeys: List[List[str]],
        non_converting_count: int = 0,
    ) -> "ShapleyAttribution":
        """Compute Shapley values from journey data.

        Args:
            converting_journeys: List of channel sequences that converted.
            non_converting_count: Number of non-converting users.
        """
        self.channels = sorted(
            set(ch for journey in converting_journeys for ch in journey)
        )

        if len(self.channels) > 12:
            raise ValueError(
                f"Shapley value is O(2^n) and infeasible with {len(self.channels)} channels. "
                f"Max supported: 12. Use MarkovAttribution instead."
            )

        total_journeys = len(converting_journeys) + non_converting_count

        # Compute coalition values: for each subset of channels,
        # what fraction of journeys convert when only those channels exist?
        all_channels = set(self.channels)
        self._coalition_values = {}

        for size in range(len(self.channels) + 1):
            for subset in combinations(self.channels, size):
                subset_set = frozenset(subset)
                if not subset_set:
                    self._coalition_values[subset_set] = 0.0
                    continue

                # Count journeys that only use channels in this subset
                converting_with_subset = sum(
                    1
                    for journey in converting_journeys
                    if set(journey).issubset(subset_set)
                )
                self._coalition_values[subset_set] = (
                    converting_with_subset / total_journeys if total_journeys > 0 else 0
                )

        # Compute Shapley values
        n = len(self.channels)
        self.channel_credits = {}

        for channel in self.channels:
            shapley_value = 0.0
            others = [ch for ch in self.channels if ch != channel]

            for size in range(len(others) + 1):
                for subset in combinations(others, size):
                    subset_set = frozenset(subset)
                    with_channel = subset_set | {channel}

                    marginal = (
                        self._coalition_values.get(with_channel, 0)
                        - self._coalition_values.get(subset_set, 0)
                    )

                    # Shapley weight: |S|! * (n - |S| - 1)! / n!
                    s = len(subset_set)
                    weight = (
                        factorial(s) * factorial(n - s - 1) / factorial(n)
                    )
                    shapley_value += weight * marginal

            self.channel_credits[channel] = max(shapley_value, 0)

        # Normalize to sum to 1
        total = sum(self.channel_credits.values())
        if total > 0:
            self.channel_credits = {
                ch: val / total for ch, val in self.channel_credits.items()
            }

        logger.info(f"Shapley values computed for {len(self.channels)} channels")
        return self

    def get_attribution(self) -> Dict[str, float]:
        """Return channel attribution weights (sum to 1.0)."""
        return dict(self.channel_credits)


class PositionBasedAttribution:
    """Position-based (U-shaped) attribution model.

    40% credit to first touch, 40% to last touch,
    remaining 20% distributed equally among middle touchpoints.
    """

    @staticmethod
    def attribute_journey(journey: List[str]) -> Dict[str, float]:
        """Attribute credit for a single journey."""
        if len(journey) == 0:
            return {}
        if len(journey) == 1:
            return {journey[0]: 1.0}
        if len(journey) == 2:
            credits = {}
            credits[journey[0]] = credits.get(journey[0], 0) + 0.5
            credits[journey[1]] = credits.get(journey[1], 0) + 0.5
            return credits

        credits: Dict[str, float] = {}
        credits[journey[0]] = credits.get(journey[0], 0) + 0.4
        credits[journey[-1]] = credits.get(journey[-1], 0) + 0.4
        middle_credit = 0.2 / (len(journey) - 2)
        for ch in journey[1:-1]:
            credits[ch] = credits.get(ch, 0) + middle_credit
        return credits

    @staticmethod
    def fit(
        converting_journeys: List[List[str]],
        non_converting_count: int = 0,
    ) -> Dict[str, float]:
        """Compute position-based attribution across all journeys."""
        total_credits: Dict[str, float] = {}
        for journey in converting_journeys:
            journey_credits = PositionBasedAttribution.attribute_journey(journey)
            for ch, credit in journey_credits.items():
                total_credits[ch] = total_credits.get(ch, 0) + credit

        total = sum(total_credits.values())
        if total > 0:
            total_credits = {ch: v / total for ch, v in total_credits.items()}
        return total_credits


def factorial(n: int) -> int:
    """Compute factorial with memoization for small values."""
    if n <= 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def run_all_models(
    impressions: pd.DataFrame,
    conversions: pd.DataFrame,
    channel_col: str = "channel",
    attribution_window_days: int = 30,
) -> pd.DataFrame:
    """Run all attribution models and return a comparison DataFrame.

    Returns:
        DataFrame with columns [channel, model, credit] for easy visualization.
    """
    from src.metrics.attribution import AttributionEngine

    journeys, non_conv = build_journeys(
        impressions, conversions, channel_col, attribution_window_days
    )

    results = []

    # Heuristic models via existing engine
    for model_name in ["last_touch", "first_touch", "linear", "time_decay"]:
        engine = AttributionEngine(model=model_name, attribution_window_days=attribution_window_days)
        attr_df = engine.attribute(impressions, conversions)
        if not attr_df.empty:
            # Map impression_id -> channel for aggregation
            imp_channels = impressions.set_index("impression_id")[channel_col].to_dict()
            attr_df["channel"] = attr_df["impression_id"].map(imp_channels)
            channel_credits = attr_df.groupby("channel")["credit"].sum()
            total = channel_credits.sum()
            if total > 0:
                channel_credits = channel_credits / total
            for ch, credit in channel_credits.items():
                results.append({"channel": ch, "model": model_name, "credit": credit})

    # Markov chain
    markov = MarkovAttribution(order=1)
    markov.fit(journeys, non_conv)
    for ch, credit in markov.get_attribution().items():
        results.append({"channel": ch, "model": "markov_chain", "credit": credit})

    # Shapley value
    shapley = ShapleyAttribution()
    shapley.fit(journeys, non_conv)
    for ch, credit in shapley.get_attribution().items():
        results.append({"channel": ch, "model": "shapley_value", "credit": credit})

    # Position-based
    position_credits = PositionBasedAttribution.fit(journeys, non_conv)
    for ch, credit in position_credits.items():
        results.append({"channel": ch, "model": "position_based", "credit": credit})

    return pd.DataFrame(results)
