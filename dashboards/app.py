"""
Ads Attribution Metrics Dashboard
==================================
Interactive Streamlit dashboard for exploring attribution models,
campaign performance, channel analysis, and data quality.

Run: streamlit run dashboards/app.py
"""
import os
import sys
from datetime import timedelta

# Ensure project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st

from dashboards.config import CUSTOM_CSS, COLORS
from dashboards.data_loader import load_data, compute_attribution_comparison
import dashboards.pages_overview as overview
import dashboards.pages_attribution as attribution
import dashboards.pages_campaigns as campaigns_page
import dashboards.pages_channels as channels_page
import dashboards.pages_quality as quality_page

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="Ads Attribution Pipeline",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<p style="font-size:18px; font-weight:500; letter-spacing:-0.02em; '
        'color:#f7f8f8; margin-bottom:4px;">Attribution Pipeline</p>'
        '<p style="font-size:12px; color:#62666d; margin-top:0;">Ads Analytics Dashboard</p>',
        unsafe_allow_html=True,
    )
    st.markdown("---")

    page = st.radio(
        "Navigation",
        [
            "Executive Overview",
            "Attribution Analysis",
            "Campaign Performance",
            "Channel & Journeys",
            "Data Quality",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")

    # Data controls
    st.markdown("### Data Controls")
    data_volume = st.select_slider(
        "Data Volume",
        options=["Small (30d)", "Medium (60d)", "Large (90d)"],
        value="Large (90d)",
    )
    days_map = {"Small (30d)": 30, "Medium (60d)": 60, "Large (90d)": 90}

    if st.button("🔄 Regenerate Data", use_container_width=True):
        # Clear parquet files so loader regenerates
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
        for f in ["impressions.parquet", "clicks.parquet", "conversions.parquet", "campaigns.parquet"]:
            path = os.path.join(data_dir, f)
            if os.path.exists(path):
                os.remove(path)
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown(
        '<p style="color: #62666d; font-size: 11px; line-height: 1.6;">'
        "7 Attribution Models<br>"
        "Streamlit + Plotly<br>"
        "Linear Design System"
        "</p>",
        unsafe_allow_html=True,
    )

# ── Load data ────────────────────────────────────────────────
campaigns, impressions, clicks, conversions = load_data()

# Apply date filter based on sidebar
n_days = days_map[data_volume]
if impressions.empty:
    st.error("No data available. Click 'Regenerate Data' in the sidebar.")
    st.stop()
max_date = impressions["date"].max()
min_date = max_date - timedelta(days=n_days)
impressions = impressions[impressions["date"] >= min_date]
clicks = clicks[clicks["date"] >= min_date]
conversions = conversions[conversions["date"] >= min_date]

# ── Render selected page ─────────────────────────────────────
if page == "Executive Overview":
    overview.render(impressions, clicks, conversions, campaigns)

elif page == "Attribution Analysis":
    with st.spinner("Running 7 attribution models..."):
        cache_key = f"{min_date}_{max_date}"
        attr_df = compute_attribution_comparison(impressions, conversions, cache_key)
    attribution.render(impressions, conversions, attr_df)

elif page == "Campaign Performance":
    campaigns_page.render(impressions, clicks, conversions, campaigns)

elif page == "Channel & Journeys":
    channels_page.render(impressions, clicks, conversions, campaigns)

elif page == "Data Quality":
    quality_page.render(impressions, clicks, conversions, campaigns)
