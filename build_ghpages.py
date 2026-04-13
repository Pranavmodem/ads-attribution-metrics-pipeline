"""
Build script: generates docs/index.html for GitHub Pages using stlite.

stlite runs Streamlit entirely in the browser via WebAssembly (Pyodide).
All Python code (dashboard pages, attribution models, data generator)
is embedded in a single HTML file — no server required.

Usage: python build_ghpages.py
Output: docs/index.html (ready for GitHub Pages)
"""
import os
import json

ROOT = os.path.dirname(os.path.abspath(__file__))

# Files to embed in stlite (order matters for __init__.py)
EMBED_FILES = {
    "src/__init__.py": "",
    "src/metrics/__init__.py": "",
    "src/utils/__init__.py": "",
    "src/metrics/attribution.py": None,
    "src/metrics/advanced_attribution.py": None,
    "src/metrics/campaign_metrics.py": None,
    "src/utils/quality_checks.py": None,
    "dashboards/__init__.py": "",
    "dashboards/config.py": None,
    "dashboards/pages_overview.py": None,
    "dashboards/pages_attribution.py": None,
    "dashboards/pages_campaigns.py": None,
    "dashboards/pages_channels.py": None,
    "dashboards/pages_quality.py": None,
}


def read_file(relpath):
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


def build_stlite_data_loader():
    """Create a stlite-compatible data loader (in-memory, no filesystem)."""
    return '''"""Data loading for stlite (in-memory, no filesystem)."""
import uuid
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

CHANNELS = {
    "Paid Search": {"ctr": 0.035, "conv_rate": 0.040, "avg_cpc": 2.50},
    "Social":      {"ctr": 0.012, "conv_rate": 0.015, "avg_cpc": 1.20},
    "Display":     {"ctr": 0.004, "conv_rate": 0.008, "avg_cpc": 0.80},
    "Video":       {"ctr": 0.018, "conv_rate": 0.012, "avg_cpc": 3.50},
    "Email":       {"ctr": 0.025, "conv_rate": 0.050, "avg_cpc": 0.30},
    "Native":      {"ctr": 0.008, "conv_rate": 0.010, "avg_cpc": 1.50},
}
CH_NAMES = list(CHANNELS.keys())
CH_WEIGHTS = [0.28, 0.24, 0.18, 0.12, 0.10, 0.08]

@st.cache_data(ttl=600)
def load_data(data_dir=""):
    np.random.seed(42)
    n_days, daily_vol = 60, 500
    start = datetime.utcnow() - timedelta(days=n_days)

    # Campaigns
    campaigns = pd.DataFrame([{
        "campaign_id": f"camp_{i:04d}",
        "campaign_name": f"Campaign {i+1}",
        "advertiser_name": f"Advertiser {np.random.randint(1,6)}",
        "channel": np.random.choice(CH_NAMES, p=CH_WEIGHTS),
        "budget_usd": np.random.choice([10000, 25000, 50000, 100000]),
        "start_date": (start + timedelta(days=np.random.randint(0, 30))).date(),
        "status": np.random.choice(["active", "active", "paused", "completed"]),
    } for i in range(15)])
    camp_ch = campaigns.set_index("campaign_id")["channel"].to_dict()
    camp_ids = campaigns["campaign_id"].tolist()

    # Impressions
    n_imp = n_days * daily_vol
    imp_camps = np.random.choice(camp_ids, n_imp)
    imp_channels = [camp_ch[c] for c in imp_camps]
    imp_cpcs = [np.random.lognormal(np.log(CHANNELS[ch]["avg_cpc"]), 0.5) for ch in imp_channels]
    impressions = pd.DataFrame({
        "impression_id": [str(uuid.uuid4()) for _ in range(n_imp)],
        "timestamp": [start + timedelta(days=np.random.randint(0, n_days),
                      hours=np.random.randint(0, 24), minutes=np.random.randint(0, 60))
                      for _ in range(n_imp)],
        "campaign_id": imp_camps,
        "channel": imp_channels,
        "placement_id": [f"pl_{np.random.randint(1,30):03d}" for _ in range(n_imp)],
        "creative_id": [f"cr_{np.random.randint(1,50):04d}" for _ in range(n_imp)],
        "user_id": [f"user_{np.random.randint(1,50000):06d}" for _ in range(n_imp)],
        "user_segment_id": [f"seg_{np.random.randint(1,20):02d}" for _ in range(n_imp)],
        "device_type": np.random.choice(["mobile","desktop","ctv","tablet"], n_imp, p=[.45,.25,.2,.1]),
        "geo_country": np.random.choice(["US","CA","UK","DE","FR","JP","BR","AU"], n_imp,
                                         p=[.40,.10,.12,.08,.08,.07,.08,.07]),
        "bid_price_usd": [round(c, 4) for c in imp_cpcs],
    })

    # Clicks
    clicks_list = []
    for ch, props in CHANNELS.items():
        ch_imps = impressions[impressions["channel"] == ch]
        n_clk = int(len(ch_imps) * props["ctr"])
        if n_clk > 0:
            sampled = ch_imps.sample(n=min(n_clk, len(ch_imps)), random_state=42)
            for _, row in sampled.head(200).iterrows():
                clicks_list.append({
                    "click_id": str(uuid.uuid4()), "impression_id": row["impression_id"],
                    "timestamp": row["timestamp"] + timedelta(seconds=np.random.randint(1,30)),
                    "campaign_id": row["campaign_id"], "channel": row["channel"],
                    "user_id": row["user_id"], "device_type": row["device_type"],
                    "geo_country": row["geo_country"],
                })
    clicks = pd.DataFrame(clicks_list) if clicks_list else pd.DataFrame(
        columns=["click_id","impression_id","timestamp","campaign_id","channel","user_id","device_type","geo_country"])

    # Conversions
    conv_list = []
    for ch, props in CHANNELS.items():
        ch_imps = impressions[impressions["channel"] == ch]
        n_conv = int(len(ch_imps) * props["conv_rate"])
        if n_conv > 0:
            sampled = ch_imps.sample(n=min(n_conv, len(ch_imps)), random_state=42)
            for _, row in sampled.head(300).iterrows():
                ct = np.random.choice(["purchase","store_visit","signup"], p=[.3,.5,.2])
                rev = round(np.random.lognormal(3, 1), 2) if ct == "purchase" else (
                    round(np.random.uniform(5, 50), 2) if ct == "store_visit" else 0.0)
                conv_list.append({
                    "conversion_id": str(uuid.uuid4()),
                    "timestamp": row["timestamp"] + timedelta(hours=int(np.random.exponential(48))),
                    "user_id": row["user_id"], "conversion_type": ct, "revenue_usd": rev,
                    "attributed_impression_id": row["impression_id"],
                    "channel": row["channel"], "campaign_id": row["campaign_id"],
                })
    conversions = pd.DataFrame(conv_list) if conv_list else pd.DataFrame(
        columns=["conversion_id","timestamp","user_id","conversion_type","revenue_usd",
                 "attributed_impression_id","channel","campaign_id"])

    impressions["timestamp"] = pd.to_datetime(impressions["timestamp"])
    clicks["timestamp"] = pd.to_datetime(clicks["timestamp"])
    conversions["timestamp"] = pd.to_datetime(conversions["timestamp"])
    impressions["date"] = impressions["timestamp"].dt.date
    clicks["date"] = clicks["timestamp"].dt.date
    conversions["date"] = conversions["timestamp"].dt.date
    return campaigns, impressions, clicks, conversions

@st.cache_data(ttl=600)
def compute_attribution_comparison(_impressions, _conversions, cache_key=""):
    from src.metrics.advanced_attribution import (
        build_journeys, MarkovAttribution, ShapleyAttribution, PositionBasedAttribution,
    )
    from src.metrics.attribution import AttributionEngine
    imp, conv = _impressions.copy(), _conversions.copy()
    if len(conv) > 1000: conv = conv.sample(1000, random_state=42)
    user_ids = set(conv["user_id"].unique())
    imp = imp[imp["user_id"].isin(user_ids)]
    results = []
    for model_name in ["last_touch", "first_touch", "linear", "time_decay"]:
        engine = AttributionEngine(model=model_name)
        attr_df = engine.attribute(imp, conv)
        if not attr_df.empty:
            ch_map = imp.set_index("impression_id")["channel"].to_dict()
            attr_df["channel"] = attr_df["impression_id"].map(ch_map)
            ch_credits = attr_df.groupby("channel")["credit"].sum()
            total = ch_credits.sum()
            if total > 0: ch_credits = ch_credits / total
            for ch, credit in ch_credits.items():
                results.append({"channel": ch, "model": model_name, "credit": credit})
    journeys, non_conv = build_journeys(imp, conv, "channel")
    if journeys:
        m = MarkovAttribution(order=1); m.fit(journeys, non_conv)
        for ch, cr in m.get_attribution().items():
            results.append({"channel": ch, "model": "markov_chain", "credit": cr})
        s = ShapleyAttribution(); s.fit(journeys, non_conv)
        for ch, cr in s.get_attribution().items():
            results.append({"channel": ch, "model": "shapley_value", "credit": cr})
        p = PositionBasedAttribution.fit(journeys, non_conv)
        for ch, cr in p.items():
            results.append({"channel": ch, "model": "position_based", "credit": cr})
    return pd.DataFrame(results) if results else pd.DataFrame(columns=["channel","model","credit"])
'''


def build_stlite_app():
    """Create stlite-compatible app.py (no filesystem ops)."""
    return '''"""Ads Attribution Dashboard (stlite version)."""
from datetime import timedelta
import streamlit as st

from dashboards.config import CUSTOM_CSS
from dashboards.data_loader import load_data, compute_attribution_comparison
import dashboards.pages_overview as overview
import dashboards.pages_attribution as attribution
import dashboards.pages_campaigns as campaigns_page
import dashboards.pages_channels as channels_page
import dashboards.pages_quality as quality_page

st.set_page_config(page_title="Ads Attribution Pipeline", page_icon="\\U0001f4ca", layout="wide", initial_sidebar_state="expanded")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        \'<p style="font-size:18px; font-weight:500; letter-spacing:-0.02em; \'
        \'color:#f7f8f8; margin-bottom:4px;">Attribution Pipeline</p>\'
        \'<p style="font-size:12px; color:#62666d; margin-top:0;">Ads Analytics Dashboard</p>\',
        unsafe_allow_html=True,
    )
    st.markdown("---")
    page = st.radio("Navigation", [
        "Executive Overview", "Attribution Analysis",
        "Campaign Performance", "Channel & Journeys", "Data Quality",
    ], label_visibility="collapsed")
    st.markdown("---")
    st.markdown(
        \'<p style="color: #62666d; font-size: 11px; line-height: 1.6;">\'
        "7 Attribution Models<br>Streamlit + Plotly<br>Linear Design System</p>",
        unsafe_allow_html=True,
    )

campaigns, impressions, clicks, conversions = load_data()
if impressions.empty:
    st.error("No data available.")
    st.stop()

if page == "Executive Overview":
    overview.render(impressions, clicks, conversions, campaigns)
elif page == "Attribution Analysis":
    with st.spinner("Running 7 attribution models..."):
        attr_df = compute_attribution_comparison(impressions, conversions, "default")
    attribution.render(impressions, conversions, attr_df)
elif page == "Campaign Performance":
    campaigns_page.render(impressions, clicks, conversions, campaigns)
elif page == "Channel & Journeys":
    channels_page.render(impressions, clicks, conversions, campaigns)
elif page == "Data Quality":
    quality_page.render(impressions, clicks, conversions, campaigns)
'''


def main():
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)

    # Collect all files
    files_js = {}
    for relpath, content in EMBED_FILES.items():
        if content is None:
            content = read_file(relpath)
        files_js[relpath] = content

    # Add stlite-specific overrides
    files_js["dashboards/data_loader.py"] = build_stlite_data_loader()
    files_js["dashboards/app.py"] = build_stlite_app()

    # Build the files JS object
    files_entries = []
    for path, content in files_js.items():
        escaped = json.dumps(content)
        files_entries.append(f'        "{path}": {escaped}')
    files_block = ",\n".join(files_entries)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Ads Attribution Pipeline — Interactive Dashboard</title>
    <meta name="description" content="Interactive ads attribution dashboard with 7 models (Markov chain, Shapley value, last-touch, etc.) running entirely in your browser." />
    <style>
        html, body {{ margin: 0; padding: 0; height: 100%; background: #08090a; overflow: hidden; }}
        #root {{ height: 100vh; }}
        #loading {{
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            background: #08090a; color: #d0d6e0; font-family: Inter, system-ui, sans-serif; z-index: 9999;
        }}
        #loading h2 {{ color: #f7f8f8; font-weight: 500; letter-spacing: -0.02em; margin-bottom: 8px; }}
        #loading p {{ color: #8a8f98; font-size: 14px; margin: 4px 0; }}
        .spinner {{
            width: 40px; height: 40px; border: 3px solid rgba(255,255,255,0.08);
            border-top: 3px solid #7170ff; border-radius: 50%;
            animation: spin 1s linear infinite; margin-bottom: 24px;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
        .progress {{ color: #62666d; font-size: 12px; margin-top: 16px; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/@stlite/mountable@0.73.0/build/stlite.js"></script>
</head>
<body>
    <div id="loading">
        <div class="spinner"></div>
        <h2>Attribution Pipeline</h2>
        <p>Loading Python runtime in your browser...</p>
        <p class="progress">This takes 15-30 seconds on first visit (cached after)</p>
    </div>
    <div id="root"></div>
    <script>
        stlite.mount({{
            requirements: ["pandas", "plotly", "numpy"],
            entrypoint: "dashboards/app.py",
            files: {{
{files_block}
            }}
        }}, document.getElementById("root")).then(() => {{
            document.getElementById("loading").style.display = "none";
        }});
    </script>
</body>
</html>"""

    outpath = os.path.join(ROOT, "docs", "index.html")
    with open(outpath, "w") as f:
        f.write(html)

    print(f"Built {outpath}")
    print(f"  Files embedded: {len(files_js)}")
    print(f"  HTML size: {len(html):,} bytes ({len(html)/1024:.0f} KB)")
    print()
    print("To deploy on GitHub Pages:")
    print("  1. Go to repo Settings > Pages")
    print("  2. Set Source: Deploy from branch")
    print("  3. Set Branch: main, Folder: /docs")
    print("  4. Save")


if __name__ == "__main__":
    main()
