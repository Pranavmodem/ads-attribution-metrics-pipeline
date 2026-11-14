"""
attribution.py
Touchpoint-level (heuristic) attribution: maps each conversion back to the
impressions that preceded it and splits the credit by a fixed rule.

Supported models:
- last_touch:  100% credit to the last impression before the conversion
- first_touch: 100% credit to the first impression in the window
- linear:      equal credit across every impression in the window
- time_decay:  credit halves for every `decay_half_life_days` before the conversion
"""
import logging
from datetime import timedelta
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

AttributionModel = Literal["last_touch", "first_touch", "linear", "time_decay"]
HEURISTIC_MODELS = ("last_touch", "first_touch", "linear", "time_decay")

OUTPUT_COLUMNS = [
    "conversion_id", "impression_id", "campaign_id", "credit", "revenue_attributed", "model",
    "impression_ts", "conversion_ts",
]


class AttributionEngine:
    """Assigns conversion credit to impressions with one heuristic model.

    The join is vectorised: conversions are merged with the same user's
    impressions, filtered to the attribution window, and credited per group.
    """

    def __init__(
        self,
        model: AttributionModel = "last_touch",
        attribution_window_days: int = 30,
        decay_half_life_days: float = 7.0,
    ):
        if model not in HEURISTIC_MODELS:
            raise ValueError(f"Unknown model: {model}. Use one of {HEURISTIC_MODELS}")
        self.model = model
        self.attribution_window = timedelta(days=attribution_window_days)
        self.decay_half_life = decay_half_life_days

    def attribute(self, impressions: pd.DataFrame, conversions: pd.DataFrame) -> pd.DataFrame:
        """Credit every conversion to the impressions in its attribution window.

        Args:
            impressions: [impression_id, user_id, timestamp, campaign_id], optional channel
            conversions: [conversion_id, user_id, timestamp, revenue_usd]

        Returns:
            One row per credited touchpoint: [conversion_id, impression_id, campaign_id,
            credit, revenue_attributed, model, impression_ts, conversion_ts], plus
            channel when impressions carry it.
            Credits for each conversion sum to 1.
        """
        extra = [c for c in ("channel",) if c in impressions.columns]
        out_cols = OUTPUT_COLUMNS + extra
        logger.info(
            f"Running {self.model} attribution: "
            f"{len(conversions):,} conversions x {len(impressions):,} impressions"
        )

        imps = impressions[["impression_id", "user_id", "timestamp", "campaign_id", *extra]].rename(
            columns={"timestamp": "imp_ts"}
        )
        convs = conversions[["conversion_id", "user_id", "timestamp", "revenue_usd"]].rename(
            columns={"timestamp": "conv_ts"}
        )
        if imps.empty or convs.empty:
            return pd.DataFrame(columns=out_cols)

        imps["imp_ts"] = pd.to_datetime(imps["imp_ts"])
        convs["conv_ts"] = pd.to_datetime(convs["conv_ts"])
        j = convs.merge(imps, on="user_id", how="inner")
        j = j[(j["imp_ts"] <= j["conv_ts"]) & (j["imp_ts"] >= j["conv_ts"] - self.attribution_window)]
        if j.empty:
            return pd.DataFrame(columns=out_cols)

        j = j.sort_values(["conversion_id", "imp_ts", "impression_id"], kind="mergesort")
        groups = j.groupby("conversion_id", sort=False)
        size = groups["impression_id"].transform("size").to_numpy()
        rank = groups.cumcount().to_numpy()

        if self.model == "last_touch":
            credit = (rank == size - 1).astype(float)
        elif self.model == "first_touch":
            credit = (rank == 0).astype(float)
        elif self.model == "linear":
            credit = 1.0 / size
        else:
            age = (j["conv_ts"] - j["imp_ts"]).dt.total_seconds().to_numpy()
            weight = np.power(0.5, age / (self.decay_half_life * 86400))
            credit = weight / pd.Series(weight, index=j.index).groupby(j["conversion_id"]).transform("sum").to_numpy()

        j = j.assign(credit=credit)
        j = j[j["credit"] > 0]
        j = j.assign(
            revenue_attributed=j["revenue_usd"] * j["credit"],
            model=self.model,
            impression_ts=j["imp_ts"],
            conversion_ts=j["conv_ts"],
        )
        result = j[out_cols].reset_index(drop=True)
        logger.info(f"Attribution complete: {len(result):,} touchpoint credits assigned")
        return result
