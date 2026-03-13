"""
attribution.py
Core attribution logic for mapping conversions back to ad impressions.

Supports multiple attribution models:
- Last-touch: 100% credit to the last impression before conversion
- First-touch: 100% credit to the first impression in the user journey
- Linear: Equal credit distributed across all touchpoints
- Time-decay: Exponentially more credit to recent touchpoints
"""
import logging
from dataclasses import dataclass
from typing import List, Literal
from datetime import timedelta

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

AttributionModel = Literal["last_touch", "first_touch", "linear", "time_decay"]


@dataclass
class AttributionResult:
    """Result of attribution for a single conversion."""
    conversion_id: str
    model: AttributionModel
    touchpoints: List[dict]  # Each: {impression_id, credit, timestamp}
    total_credit: float  # Should sum to 1.0


class AttributionEngine:
    """Computes attribution across multiple models.

    Given a set of impressions and conversions for a user,
    assigns credit to each impression based on the selected model.
    """

    def __init__(
        self,
        model: AttributionModel = "last_touch",
        attribution_window_days: int = 30,
        decay_half_life_days: float = 7.0,
    ):
        self.model = model
        self.attribution_window = timedelta(days=attribution_window_days)
        self.decay_half_life = decay_half_life_days

    def attribute(
        self,
        impressions: pd.DataFrame,
        conversions: pd.DataFrame,
    ) -> pd.DataFrame:
        """Run attribution for all conversions against their impression history.

        Args:
            impressions: DataFrame with columns [impression_id, user_id, timestamp, campaign_id]
            conversions: DataFrame with columns [conversion_id, user_id, timestamp, revenue_usd]

        Returns:
            DataFrame with columns [conversion_id, impression_id, credit, revenue_attributed]
        """
        logger.info(
            f"Running {self.model} attribution: "
            f"{len(conversions):,} conversions × {len(impressions):,} impressions"
        )

        results = []

        for _, conversion in conversions.iterrows():
            # Find impressions for this user within the attribution window
            user_impressions = impressions[
                (impressions["user_id"] == conversion["user_id"])
                & (impressions["timestamp"] <= conversion["timestamp"])
                & (impressions["timestamp"] >= conversion["timestamp"] - self.attribution_window)
            ].sort_values("timestamp")

            if user_impressions.empty:
                continue

            credits = self._compute_credits(user_impressions, conversion)

            for _, imp in user_impressions.iterrows():
                imp_credit = credits.get(imp["impression_id"], 0.0)
                if imp_credit > 0:
                    results.append({
                        "conversion_id": conversion["conversion_id"],
                        "impression_id": imp["impression_id"],
                        "campaign_id": imp["campaign_id"],
                        "credit": imp_credit,
                        "revenue_attributed": conversion["revenue_usd"] * imp_credit,
                        "model": self.model,
                    })

        result_df = pd.DataFrame(results)
        logger.info(f"Attribution complete: {len(result_df):,} touchpoint credits assigned")
        return result_df

    def _compute_credits(
        self, impressions: pd.DataFrame, conversion: pd.Series
    ) -> dict:
        """Compute credit allocation based on the selected model."""
        model_fn = {
            "last_touch": self._last_touch,
            "first_touch": self._first_touch,
            "linear": self._linear,
            "time_decay": self._time_decay,
        }

        if self.model not in model_fn:
            raise ValueError(f"Unknown model: {self.model}")

        return model_fn[self.model](impressions, conversion)

    def _last_touch(self, impressions: pd.DataFrame, conversion: pd.Series) -> dict:
        """100% credit to the last impression before conversion."""
        last_imp = impressions.iloc[-1]
        return {last_imp["impression_id"]: 1.0}

    def _first_touch(self, impressions: pd.DataFrame, conversion: pd.Series) -> dict:
        """100% credit to the first impression in the journey."""
        first_imp = impressions.iloc[0]
        return {first_imp["impression_id"]: 1.0}

    def _linear(self, impressions: pd.DataFrame, conversion: pd.Series) -> dict:
        """Equal credit across all touchpoints."""
        n = len(impressions)
        credit = 1.0 / n
        return {row["impression_id"]: credit for _, row in impressions.iterrows()}

    def _time_decay(self, impressions: pd.DataFrame, conversion: pd.Series) -> dict:
        """Exponentially more credit to impressions closer to conversion.

        Uses a half-life decay: impressions N half-lives ago get 1/2^N credit.
        """
        conversion_time = conversion["timestamp"]
        half_life_seconds = self.decay_half_life * 86400  # days → seconds

        raw_weights = {}
        for _, imp in impressions.iterrows():
            time_diff = (conversion_time - imp["timestamp"]).total_seconds()
            weight = np.exp(-0.693 * time_diff / half_life_seconds)  # ln(2) ≈ 0.693
            raw_weights[imp["impression_id"]] = weight

        # Normalize to sum to 1.0
        total = sum(raw_weights.values())
        return {k: v / total for k, v in raw_weights.items()} if total > 0 else raw_weights
