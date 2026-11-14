"""
advanced_attribution.py
Journey-level attribution models: Markov chain, Shapley value, and position-based.

All three take the same input: the channel paths of users who converted and
the channel paths of users who did not. Non-converting paths matter. Without
them a Markov chain has no way to see that a channel leads nowhere, and a
Shapley model has no baseline to measure lift against.

References:
- Markov removal effect: Anderl et al. (2016), "Mapping the customer journey";
  implemented in ChannelAttribution (https://github.com/DavideAltomare/ChannelAttribution).
- Shapley value over a conversion model: Dalessandro et al. (2012),
  "Causally motivated attribution for online advertising".
"""
import logging
from collections import Counter
from math import factorial
from typing import Callable, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

Journey = List[str]

START, CONVERSION, NULL = "(start)", "(conversion)", "(null)"


def build_journeys(
    impressions: pd.DataFrame,
    conversions: pd.DataFrame,
    channel_col: str = "channel",
    attribution_window_days: int = 30,
) -> Tuple[List[Journey], List[Journey]]:
    """Turn impression logs into ordered channel paths, one per user.

    Both kinds of path use the same lookback window. A converting user's path
    holds the impressions in the window before their first conversion; a
    non-converting user's path holds the impressions in the window before their
    last impression. Windowing only one side would bias the models: long-running
    upper-funnel exposure would survive on non-converting paths and be cut from
    converting ones, making those channels look like they hurt conversion.

    Returns:
        (converting_journeys, non_converting_journeys)
    """
    imps = impressions[["user_id", "timestamp", channel_col]].copy()
    imps["timestamp"] = pd.to_datetime(imps["timestamp"])
    first_conv = (
        conversions.assign(timestamp=pd.to_datetime(conversions["timestamp"]))
        .groupby("user_id")["timestamp"]
        .min()
        .rename("conv_ts")
    )
    imps = imps.merge(first_conv, left_on="user_id", right_index=True, how="left")
    last_seen = imps.groupby("user_id")["timestamp"].transform("max")
    imps["anchor"] = imps["conv_ts"].fillna(last_seen)

    window = pd.Timedelta(days=attribution_window_days)
    imps = imps[(imps["timestamp"] <= imps["anchor"]) & (imps["timestamp"] >= imps["anchor"] - window)]
    imps = imps.sort_values(["user_id", "timestamp"], kind="mergesort")

    paths = imps.groupby("user_id", sort=False).agg(
        path=(channel_col, list), converted=("conv_ts", "first")
    )
    is_conv = paths["converted"].notna()
    converting = paths.loc[is_conv, "path"].tolist()
    non_converting = paths.loc[~is_conv, "path"].tolist()

    logger.info(
        f"Built {len(converting):,} converting and {len(non_converting):,} non-converting journeys"
    )
    return converting, non_converting


class MarkovAttribution:
    """Markov chain attribution with the removal effect.

    Every journey becomes a walk (start) -> channel -> ... -> (conversion) or
    (null). Transition counts become probabilities, and the probability of
    reaching (conversion) from (start) is solved exactly as an absorbing chain.
    A channel's removal effect is the share of that probability lost when the
    channel is deleted and every transition into it is sent to (null).

    With order > 1 a state is the tuple of the last `order` channels, so the
    model can tell "Display then Paid Search" apart from "Paid Search alone".
    """

    def __init__(self, order: int = 1):
        if order < 1:
            raise ValueError("order must be >= 1")
        self.order = order
        self.channels: List[str] = []
        self.transition_matrix: Dict[tuple, Dict[tuple, float]] = {}
        self.conversion_probability: float = 0.0
        self.removal_effects: Dict[str, float] = {}

    def _states(self, journey: Sequence[str]) -> List[tuple]:
        k = self.order
        return [tuple(journey[max(0, i - k + 1): i + 1]) for i in range(len(journey))]

    def fit(
        self,
        converting_journeys: List[Journey],
        non_converting_journeys: List[Journey],
    ) -> "MarkovAttribution":
        self.channels = sorted({ch for j in converting_journeys for ch in j})

        counts: Counter = Counter()
        for journeys, end in ((converting_journeys, CONVERSION), (non_converting_journeys, NULL)):
            for journey in journeys:
                if not journey:
                    continue
                path = [(START,)] + self._states(journey) + [(end,)]
                counts.update(zip(path, path[1:]))

        totals: Counter = Counter()
        for (src, _), n in counts.items():
            totals[src] += n
        self.transition_matrix = {}
        for (src, dst), n in counts.items():
            self.transition_matrix.setdefault(src, {})[dst] = n / totals[src]

        self.conversion_probability = self._conversion_probability(self.transition_matrix)
        raw = {}
        for channel in self.channels:
            without = self._remove_channel(self.transition_matrix, channel)
            p = self._conversion_probability(without)
            base = self.conversion_probability
            raw[channel] = max((base - p) / base, 0.0) if base > 0 else 0.0

        total = sum(raw.values())
        self.removal_effects = {ch: v / total for ch, v in raw.items()} if total > 0 else raw
        logger.info(
            f"Markov (order {self.order}) fitted on {len(self.transition_matrix)} states; "
            f"P(conversion) = {self.conversion_probability:.4f}"
        )
        return self

    def get_attribution(self) -> Dict[str, float]:
        """Channel credit shares, summing to 1."""
        return dict(self.removal_effects)

    @staticmethod
    def _conversion_probability(matrix: Dict[tuple, Dict[tuple, float]]) -> float:
        """P(reach (conversion) from (start)), solved as an absorbing Markov chain."""
        start = (START,)
        if start not in matrix:
            return 0.0
        absorbing = {(CONVERSION,), (NULL,)}
        transient = [s for s in matrix if s not in absorbing]
        index = {s: i for i, s in enumerate(transient)}
        n = len(transient)

        q = np.zeros((n, n))
        r = np.zeros(n)
        for src, dsts in matrix.items():
            i = index[src]
            for dst, p in dsts.items():
                if dst in index:
                    q[i, index[dst]] = p
                elif dst == (CONVERSION,):
                    r[i] = p
        try:
            absorbed = np.linalg.solve(np.eye(n) - q, r)
        except np.linalg.LinAlgError:
            return 0.0
        return float(absorbed[index[start]])

    @staticmethod
    def _remove_channel(
        matrix: Dict[tuple, Dict[tuple, float]], channel: str
    ) -> Dict[tuple, Dict[tuple, float]]:
        """Delete every state that contains `channel`; traffic into it goes to (null)."""
        modified = {}
        for src, dsts in matrix.items():
            if channel in src:
                continue
            new = {}
            for dst, p in dsts.items():
                key = (NULL,) if channel in dst else dst
                new[key] = new.get(key, 0.0) + p
            modified[src] = new
        return modified


def exposure_shapley(
    exposure: np.ndarray,
    logit_fn: Callable[[np.ndarray], np.ndarray],
) -> np.ndarray:
    """Per-user Shapley values of a conversion-probability model, summed over users.

    For each user the "players" are the channels that reached them, and the value
    of a coalition S is P(convert | only S reached them) - P(convert | nothing did).
    The Shapley value splits that user's lift across their channels exactly
    (efficiency), so summing over users gives each channel's expected number of
    incremental conversions.

    Args:
        exposure: (n_users, n_channels) impression counts per channel.
        logit_fn: maps a counts matrix of the same shape to conversion log-odds.

    Returns:
        (n_channels,) expected incremental conversions per channel.
    """
    n_users, k = exposure.shape
    exposed = exposure > 0
    n_exposed = exposed.sum(axis=1)
    masks = np.array([[(m >> c) & 1 for c in range(k)] for m in range(2**k)], dtype=bool)

    # P(convert) for every user under every coalition (cheap for k <= 12).
    probs = np.empty((2**k, n_users))
    for m, mask in enumerate(masks):
        probs[m] = 1.0 / (1.0 + np.exp(-logit_fn(exposure * mask)))

    fact = np.array([factorial(i) for i in range(k + 1)], dtype=float)
    credit = np.zeros(k)
    for m, mask in enumerate(masks):
        size = int(mask.sum())
        is_subset = ~(mask & ~exposed).any(axis=1)  # coalition only uses channels the user saw
        for c in range(k):
            if mask[c]:
                continue
            ok = is_subset & exposed[:, c]
            if not ok.any():
                continue
            n = n_exposed[ok]
            weight = fact[size] * fact[n - size - 1] / fact[n]
            marginal = probs[m | (1 << c), ok] - probs[m, ok]
            credit[c] += float((weight * marginal).sum())
    return credit


def _fit_logistic(x: np.ndarray, y: np.ndarray, ridge: float = 1.0, iters: int = 50) -> np.ndarray:
    """L2-regularised logistic regression by Newton's method. Returns [intercept, *coefs]."""
    x1 = np.column_stack([np.ones(len(x)), x])
    w = np.zeros(x1.shape[1])
    penalty = np.full(x1.shape[1], ridge)
    penalty[0] = 0.0  # never shrink the intercept
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(x1 @ w)))
        grad = x1.T @ (y - p) - penalty * w
        hess = (x1 * (p * (1 - p))[:, None]).T @ x1 + np.diag(penalty)
        step = np.linalg.solve(hess, grad)
        w += step
        if np.abs(step).max() < 1e-8:
            break
    return w


def exposure_matrix(journeys: List[Journey], channels: List[str]) -> np.ndarray:
    """(n_journeys, n_channels) count of impressions per channel."""
    col = {ch: i for i, ch in enumerate(channels)}
    m = np.zeros((len(journeys), len(channels)))
    for row, journey in enumerate(journeys):
        for ch, n in Counter(journey).items():
            if ch in col:
                m[row, col[ch]] = n
    return m


class ShapleyAttribution:
    """Shapley value attribution over a fitted conversion model.

    Fits P(convert | which channels reached the user) with a logistic regression
    on every user, converting or not, then splits each user's predicted lift
    across the channels that reached them with exact Shapley values.

    The older "simplified Shapley" (counting converting journeys whose channel set
    fits inside each coalition) ignores non-converters, and it provably reduces to
    an even split over each journey's distinct channels, i.e. linear attribution.
    """

    MAX_CHANNELS = 12

    def __init__(self, ridge: float = 1.0):
        self.ridge = ridge
        self.channels: List[str] = []
        self.coefficients: Dict[str, float] = {}
        self.intercept: float = 0.0
        self.channel_credits: Dict[str, float] = {}

    def fit(
        self,
        converting_journeys: List[Journey],
        non_converting_journeys: List[Journey],
    ) -> "ShapleyAttribution":
        journeys = converting_journeys + non_converting_journeys
        self.channels = sorted({ch for j in journeys for ch in j})
        if len(self.channels) > self.MAX_CHANNELS:
            raise ValueError(
                f"Exact Shapley is O(2^n); {len(self.channels)} channels is too many "
                f"(max {self.MAX_CHANNELS}). Use MarkovAttribution instead."
            )

        counts = exposure_matrix(journeys, self.channels)
        exposed = (counts > 0).astype(float)
        y = np.r_[np.ones(len(converting_journeys)), np.zeros(len(non_converting_journeys))]
        w = _fit_logistic(exposed, y, ridge=self.ridge)
        self.intercept = float(w[0])
        self.coefficients = dict(zip(self.channels, w[1:].tolist()))

        credit = exposure_shapley(counts, lambda c: w[0] + (c > 0) @ w[1:])
        credit = np.clip(credit, 0, None)
        total = credit.sum()
        shares = credit / total if total > 0 else credit
        self.channel_credits = dict(zip(self.channels, shares.tolist()))
        logger.info(f"Shapley values computed for {len(self.channels)} channels")
        return self

    def get_attribution(self) -> Dict[str, float]:
        """Channel credit shares, summing to 1."""
        return dict(self.channel_credits)


class PositionBasedAttribution:
    """Position-based (U-shaped) attribution: a fixed rule, not a learned model.

    40% to the first touch, 40% to the last, 20% split across the middle.
    """

    @staticmethod
    def attribute_journey(journey: Journey) -> Dict[str, float]:
        if not journey:
            return {}
        if len(journey) == 1:
            return {journey[0]: 1.0}
        if len(journey) == 2:
            weights = [0.5, 0.5]
        else:
            middle = 0.2 / (len(journey) - 2)
            weights = [0.4] + [middle] * (len(journey) - 2) + [0.4]
        credits: Dict[str, float] = {}
        for ch, w in zip(journey, weights):
            credits[ch] = credits.get(ch, 0.0) + w
        return credits

    @staticmethod
    def fit(
        converting_journeys: List[Journey],
        non_converting_journeys: List[Journey] = None,
    ) -> Dict[str, float]:
        """Channel credit shares across all converting journeys (non-converters are ignored)."""
        totals: Dict[str, float] = {}
        for journey in converting_journeys:
            for ch, c in PositionBasedAttribution.attribute_journey(journey).items():
                totals[ch] = totals.get(ch, 0.0) + c
        total = sum(totals.values())
        return {ch: v / total for ch, v in totals.items()} if total > 0 else totals
