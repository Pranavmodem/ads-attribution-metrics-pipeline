"""
Data loading and caching for the dashboard.
"""
import os
import sys
import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@st.cache_data(ttl=300)
def load_data(data_dir: str = "data/raw/"):
    """Load all datasets, generate if missing."""
    abs_dir = os.path.join(os.path.dirname(__file__), "..", data_dir)
    imp_path = os.path.join(abs_dir, "impressions.parquet")

    if not os.path.exists(imp_path):
        st.info("Generating synthetic data (first run)...")
        from src.utils.data_generator import (
            generate_campaigns, generate_impressions,
            generate_clicks, generate_conversions,
        )
        os.makedirs(abs_dir, exist_ok=True)
        campaigns = generate_campaigns(20)
        impressions = generate_impressions(campaigns, n_days=90, impressions_per_day=2000)
        clicks = generate_clicks(impressions)
        conversions = generate_conversions(impressions)
        campaigns.to_parquet(os.path.join(abs_dir, "campaigns.parquet"), index=False)
        impressions.to_parquet(os.path.join(abs_dir, "impressions.parquet"), index=False)
        clicks.to_parquet(os.path.join(abs_dir, "clicks.parquet"), index=False)
        conversions.to_parquet(os.path.join(abs_dir, "conversions.parquet"), index=False)
    else:
        campaigns = pd.read_parquet(os.path.join(abs_dir, "campaigns.parquet"))
        impressions = pd.read_parquet(os.path.join(abs_dir, "impressions.parquet"))
        clicks = pd.read_parquet(os.path.join(abs_dir, "clicks.parquet"))
        conversions = pd.read_parquet(os.path.join(abs_dir, "conversions.parquet"))

    impressions["timestamp"] = pd.to_datetime(impressions["timestamp"])
    clicks["timestamp"] = pd.to_datetime(clicks["timestamp"])
    conversions["timestamp"] = pd.to_datetime(conversions["timestamp"])
    impressions["date"] = impressions["timestamp"].dt.date
    clicks["date"] = clicks["timestamp"].dt.date
    conversions["date"] = conversions["timestamp"].dt.date

    return campaigns, impressions, clicks, conversions


@st.cache_data(ttl=600)
def compute_attribution_comparison(_impressions, _conversions):
    """Run all attribution models for comparison. Underscore prefix = unhashable."""
    from src.metrics.advanced_attribution import (
        build_journeys, MarkovAttribution, ShapleyAttribution,
        PositionBasedAttribution,
    )
    from src.metrics.attribution import AttributionEngine

    imp = _impressions.copy()
    conv = _conversions.copy()

    # Sample for performance (Shapley is O(2^n) on channels)
    if len(conv) > 3000:
        conv = conv.sample(3000, random_state=42)
    if len(imp) > 50000:
        user_ids = set(conv["user_id"].unique())
        imp = imp[imp["user_id"].isin(user_ids) | (imp.index.isin(imp.sample(min(50000, len(imp)), random_state=42).index))]

    results = []

    # Heuristic models
    for model_name in ["last_touch", "first_touch", "linear", "time_decay"]:
        engine = AttributionEngine(model=model_name)
        attr_df = engine.attribute(imp, conv)
        if not attr_df.empty:
            ch_map = imp.set_index("impression_id")["channel"].to_dict()
            attr_df["channel"] = attr_df["impression_id"].map(ch_map)
            ch_credits = attr_df.groupby("channel")["credit"].sum()
            total = ch_credits.sum()
            if total > 0:
                ch_credits = ch_credits / total
            for ch, credit in ch_credits.items():
                results.append({"channel": ch, "model": model_name, "credit": credit})

    # Data-driven models
    journeys, non_conv = build_journeys(imp, conv, "channel")

    if journeys:
        markov = MarkovAttribution(order=1)
        markov.fit(journeys, non_conv)
        for ch, credit in markov.get_attribution().items():
            results.append({"channel": ch, "model": "markov_chain", "credit": credit})

        shapley = ShapleyAttribution()
        shapley.fit(journeys, non_conv)
        for ch, credit in shapley.get_attribution().items():
            results.append({"channel": ch, "model": "shapley_value", "credit": credit})

        pos_credits = PositionBasedAttribution.fit(journeys, non_conv)
        for ch, credit in pos_credits.items():
            results.append({"channel": ch, "model": "position_based", "credit": credit})

    return pd.DataFrame(results) if results else pd.DataFrame(columns=["channel", "model", "credit"])
