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

from dashboards.config import CUSTOM_CSS
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
    # Logo / brand
    st.markdown(
        '<div style="padding: 4px 0 20px 0;">'
        '<div style="display:flex; align-items:center; gap:10px; margin-bottom:2px;">'
        '<div style="width:28px; height:28px; border-radius:6px; background:linear-gradient(135deg,#5e6ad2,#7170ff); '
        'display:flex; align-items:center; justify-content:center; flex-shrink:0;">'
        '<span style="color:#fff !important; font-size:14px; font-weight:600;">A</span></div>'
        '<div><span style="color:#f7f8f8 !important; font-size:15px; font-weight:500; '
        'letter-spacing:-0.02em;">Attribution Pipeline</span></div></div>'
        '<p style="color:#62666d !important; font-size:11px; margin:4px 0 0 38px; letter-spacing:0.02em;">ADS ANALYTICS</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div style="border-top:1px solid rgba(255,255,255,0.05); margin:0 0 16px 0;"></div>', unsafe_allow_html=True)

    # Navigation
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

    st.markdown('<div style="border-top:1px solid rgba(255,255,255,0.05); margin:20px 0 16px 0;"></div>', unsafe_allow_html=True)

    # Data controls
    st.markdown('<p style="color:#62666d !important; font-size:11px; font-weight:500; letter-spacing:0.05em; margin-bottom:8px;">DATA CONTROLS</p>', unsafe_allow_html=True)
    data_volume = st.select_slider(
        "Data Volume",
        options=["Small (30d)", "Medium (60d)", "Large (90d)"],
        value="Large (90d)",
    )
    days_map = {"Small (30d)": 30, "Medium (60d)": 60, "Large (90d)": 90}

    if st.button("Regenerate Data", use_container_width=True):
        data_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
        for f in ["impressions.parquet", "clicks.parquet", "conversions.parquet", "campaigns.parquet"]:
            path = os.path.join(data_dir, f)
            if os.path.exists(path):
                os.remove(path)
        st.cache_data.clear()
        st.rerun()

    # Footer
    st.markdown(
        '<div style="position:fixed; bottom:20px; left:16px; width:220px;">'
        '<div style="border-top:1px solid rgba(255,255,255,0.05); padding-top:12px;">'
        '<p style="color:#3e3e44 !important; font-size:10px; line-height:1.5; letter-spacing:0.02em; margin:0;">'
        '7 MODELS &middot; STREAMLIT + PLOTLY<br>LINEAR DESIGN SYSTEM</p>'
        '</div></div>',
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
