"""
compare.py
Runs every attribution model on the same impressions and conversions.

Used by the dbt Python models in models/attribution/ and by the tests, so the
warehouse and the test suite exercise exactly the same code.
"""
from typing import Optional

import pandas as pd

from src.metrics.advanced_attribution import (
    MarkovAttribution,
    PositionBasedAttribution,
    ShapleyAttribution,
    build_journeys,
)
from src.metrics.attribution import HEURISTIC_MODELS, AttributionEngine

# model -> (label, family). Position-based is a fixed rule, so it is a heuristic.
MODELS = {
    "last_touch": ("Last touch", "heuristic"),
    "first_touch": ("First touch", "heuristic"),
    "linear": ("Linear", "heuristic"),
    "time_decay": ("Time decay", "heuristic"),
    "position_based": ("Position-based", "heuristic"),
    "markov_chain": ("Markov chain", "data-driven"),
    "shapley_value": ("Shapley value", "data-driven"),
}


def touchpoint_credits(
    impressions: pd.DataFrame, conversions: pd.DataFrame, window_days: int = 30
) -> pd.DataFrame:
    """Impression-level credit from every heuristic model, stacked."""
    frames = [
        AttributionEngine(model, attribution_window_days=window_days).attribute(impressions, conversions)
        for model in HEURISTIC_MODELS
    ]
    return pd.concat([f for f in frames if len(f)], ignore_index=True)


def channel_credits(
    impressions: pd.DataFrame,
    conversions: pd.DataFrame,
    window_days: int = 30,
    touchpoints: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Channel credit shares (summing to 1 per model) for all seven models.

    Pass `touchpoints` from `touchpoint_credits` to reuse it instead of
    recomputing the heuristic models.
    """
    if touchpoints is None:
        touchpoints = touchpoint_credits(impressions, conversions, window_days)

    heuristic = touchpoints.groupby(["model", "channel"], as_index=False)["credit"].sum()
    heuristic["credit"] /= heuristic.groupby("model")["credit"].transform("sum")

    converting, non_converting = build_journeys(
        impressions, conversions, attribution_window_days=window_days
    )
    journey_models = {
        "position_based": PositionBasedAttribution.fit(converting, non_converting),
        "markov_chain": MarkovAttribution(order=1).fit(converting, non_converting).get_attribution(),
        "shapley_value": ShapleyAttribution().fit(converting, non_converting).get_attribution(),
    }
    rows = [
        {"model": model, "channel": channel, "credit": credit}
        for model, credits in journey_models.items()
        for channel, credit in credits.items()
    ]
    out = pd.concat([heuristic, pd.DataFrame(rows)], ignore_index=True)
    out["model_label"] = out["model"].map(lambda m: MODELS[m][0])
    out["model_family"] = out["model"].map(lambda m: MODELS[m][1])
    return out.sort_values(["model", "channel"]).reset_index(drop=True)
