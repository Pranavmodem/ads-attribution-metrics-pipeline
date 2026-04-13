"""
campaign_metrics.py
Computes core advertising business metrics from attributed data.

These are the metrics that business stakeholders self-serve via dashboards.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


class CampaignMetrics:
    """Calculates standard ad campaign performance metrics.

    Input: joined impression + conversion + attribution data.
    Output: campaign-level metric aggregations for the marts layer.
    """

    def compute_all(
        self,
        impressions: pd.DataFrame,
        clicks: pd.DataFrame,
        attributions: pd.DataFrame,
        campaigns: pd.DataFrame,
    ) -> pd.DataFrame:
        """Compute all campaign-level metrics.

        Returns a DataFrame with one row per campaign per date, containing:
        - impressions, clicks, conversions, spend, revenue
        - CPM, CTR, conversion_rate, ROAS, CPA
        - fill_rate, avg_frequency, viewability_rate
        """
        # Aggregate impressions by campaign + date
        imp_agg = (
            impressions.assign(date=impressions["timestamp"].dt.date)
            .groupby(["campaign_id", "date"])
            .agg(
                total_impressions=("impression_id", "count"),
                total_spend=("bid_price_usd", "sum"),
                unique_users=("user_id", "nunique"),
            )
            .reset_index()
        )

        # Aggregate clicks
        click_agg = (
            clicks.assign(date=clicks["timestamp"].dt.date)
            .groupby(["campaign_id", "date"])
            .agg(total_clicks=("click_id", "count"))
            .reset_index()
        )

        # Aggregate attributed conversions and revenue
        conv_agg = (
            attributions.groupby(["campaign_id"])
            .agg(
                total_conversions=("conversion_id", "nunique"),
                total_revenue_attributed=("revenue_attributed", "sum"),
            )
            .reset_index()
        )

        # Join everything
        metrics = imp_agg.merge(click_agg, on=["campaign_id", "date"], how="left")
        metrics = metrics.merge(conv_agg, on=["campaign_id"], how="left")
        metrics = metrics.merge(
            campaigns[["campaign_id", "campaign_name", "advertiser_name"]],
            on="campaign_id",
            how="left",
        )

        # Fill NAs
        metrics["total_clicks"] = metrics["total_clicks"].fillna(0).astype(int)
        metrics["total_conversions"] = metrics["total_conversions"].fillna(0).astype(int)
        metrics["total_revenue_attributed"] = metrics["total_revenue_attributed"].fillna(0.0)

        # Compute derived metrics
        metrics["cpm"] = (metrics["total_spend"] / metrics["total_impressions"]) * 1000
        metrics["ctr"] = metrics["total_clicks"] / metrics["total_impressions"]
        metrics["conversion_rate"] = metrics.apply(
            lambda r: r["total_conversions"] / r["total_clicks"] if r["total_clicks"] > 0 else 0,
            axis=1,
        )
        metrics["roas"] = metrics.apply(
            lambda r: r["total_revenue_attributed"] / r["total_spend"] if r["total_spend"] > 0 else 0,
            axis=1,
        )
        metrics["cpa"] = metrics.apply(
            lambda r: r["total_spend"] / r["total_conversions"] if r["total_conversions"] > 0 else None,
            axis=1,
        )
        metrics["avg_frequency"] = metrics["total_impressions"] / metrics["unique_users"]

        logger.info(f"Computed metrics for {len(metrics):,} campaign-date combinations")
        return metrics

    @staticmethod
    def compute_fill_rate(
        available_inventory: pd.DataFrame, filled_impressions: pd.DataFrame
    ) -> pd.DataFrame:
        """Compute fill rate: what % of available ad slots were actually filled.

        Fill rate = filled impressions / available inventory slots.
        Critical metric for supply-side optimization.
        """
        inventory_agg = (
            available_inventory.groupby(["placement_id", "date"])
            .agg(available_slots=("slot_id", "count"))
            .reset_index()
        )

        filled_agg = (
            filled_impressions.groupby(["placement_id", "date"])
            .agg(filled_slots=("impression_id", "count"))
            .reset_index()
        )

        fill_rate = inventory_agg.merge(filled_agg, on=["placement_id", "date"], how="left")
        fill_rate["filled_slots"] = fill_rate["filled_slots"].fillna(0)
        fill_rate["fill_rate"] = fill_rate["filled_slots"] / fill_rate["available_slots"]

        return fill_rate
