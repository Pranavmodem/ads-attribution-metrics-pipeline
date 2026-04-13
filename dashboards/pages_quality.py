"""Data Quality & Pipeline Health (Linear dark theme)."""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboards.config import COLORS, metric_card, apply_linear_layout


def render(impressions, clicks, conversions, campaigns):
    st.markdown('<div class="section-header">Data Quality & Pipeline Health</div>', unsafe_allow_html=True)

    imp_nulls = impressions.isnull().sum().sum()
    imp_dups = impressions["impression_id"].duplicated().sum()
    conv_nulls = conversions.isnull().sum().sum()
    max_ts = impressions["timestamp"].max()
    now = pd.Timestamp.now()
    if hasattr(max_ts, 'tzinfo') and max_ts.tzinfo is not None:
        max_ts = max_ts.replace(tzinfo=None)
    freshness_hours = max((now - max_ts).total_seconds() / 3600, 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        color = COLORS["green"] if imp_nulls == 0 else COLORS["red"]
        st.markdown(metric_card("Impression Nulls", f"{imp_nulls:,}", accent_color=color), unsafe_allow_html=True)
    with c2:
        color = COLORS["green"] if imp_dups == 0 else COLORS["amber"]
        st.markdown(metric_card("Duplicate Impressions", f"{imp_dups:,}", accent_color=color), unsafe_allow_html=True)
    with c3:
        color = COLORS["green"] if conv_nulls == 0 else COLORS["red"]
        st.markdown(metric_card("Conversion Nulls", f"{conv_nulls:,}", accent_color=color), unsafe_allow_html=True)
    with c4:
        color = COLORS["green"] if freshness_hours < 48 else COLORS["amber"]
        st.markdown(metric_card("Data Freshness", f"{freshness_hours:.0f}h ago", accent_color=color), unsafe_allow_html=True)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Impression Completeness")
        imp_complete = (1 - impressions.isnull().mean()).reset_index()
        imp_complete.columns = ["column", "completeness"]
        imp_complete["pct"] = imp_complete["completeness"] * 100
        colors = [COLORS["green"] if v >= 99 else COLORS["amber"] if v >= 95 else COLORS["red"] for v in imp_complete["pct"]]
        fig = go.Figure(go.Bar(
            y=imp_complete["column"], x=imp_complete["pct"], orientation="h",
            marker_color=colors, marker_line_width=0,
            text=[f"{v:.1f}%" for v in imp_complete["pct"]], textposition="inside",
            textfont=dict(color="#f7f8f8", size=11),
        ))
        fig.add_vline(x=95, line_dash="dash", line_color="#3e3e44")
        apply_linear_layout(fig, height=320)
        fig.update_layout(xaxis=dict(range=[80, 101]))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Conversion Completeness")
        conv_complete = (1 - conversions.isnull().mean()).reset_index()
        conv_complete.columns = ["column", "completeness"]
        conv_complete["pct"] = conv_complete["completeness"] * 100
        colors = [COLORS["green"] if v >= 99 else COLORS["amber"] if v >= 95 else COLORS["red"] for v in conv_complete["pct"]]
        fig2 = go.Figure(go.Bar(
            y=conv_complete["column"], x=conv_complete["pct"], orientation="h",
            marker_color=colors, marker_line_width=0,
            text=[f"{v:.1f}%" for v in conv_complete["pct"]], textposition="inside",
            textfont=dict(color="#f7f8f8", size=11),
        ))
        fig2.add_vline(x=95, line_dash="dash", line_color="#3e3e44")
        apply_linear_layout(fig2, height=320)
        fig2.update_layout(xaxis=dict(range=[80, 101]))
        st.plotly_chart(fig2, use_container_width=True)

    # Anomaly detection
    st.subheader("Daily Volume (Anomaly Detection)")
    daily_vol = impressions.groupby("date").size().reset_index(name="count")
    mean_vol = daily_vol["count"].mean()
    std_vol = daily_vol["count"].std()
    if pd.notna(std_vol) and std_vol > 0:
        daily_vol["z_score"] = (daily_vol["count"] - mean_vol) / std_vol
    else:
        daily_vol["z_score"] = 0.0
    daily_vol["anomaly"] = daily_vol["z_score"].abs() > 2

    fig3 = go.Figure()
    normal = daily_vol[~daily_vol["anomaly"]]
    anomalies = daily_vol[daily_vol["anomaly"]]
    fig3.add_trace(go.Scatter(
        x=normal["date"], y=normal["count"], mode="lines+markers",
        name="Normal", line=dict(color=COLORS["accent"], width=1.5),
        marker=dict(size=3, color=COLORS["accent"]),
    ))
    if not anomalies.empty:
        fig3.add_trace(go.Scatter(
            x=anomalies["date"], y=anomalies["count"], mode="markers",
            name="Anomaly", marker=dict(color=COLORS["red"], size=10, symbol="x"),
        ))
    fig3.add_hline(y=mean_vol, line_dash="dash", line_color="#3e3e44",
                   annotation_text="Mean", annotation_font_color="#8a8f98")
    fig3.add_hline(y=mean_vol + 2 * std_vol, line_dash="dot", line_color=COLORS["amber"],
                   annotation_text="+2\u03c3", annotation_font_color="#8a8f98")
    fig3.add_hline(y=mean_vol - 2 * std_vol, line_dash="dot", line_color=COLORS["amber"],
                   annotation_text="-2\u03c3", annotation_font_color="#8a8f98")
    apply_linear_layout(fig3, height=340)
    st.plotly_chart(fig3, use_container_width=True)

    # Distributions
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Revenue Distribution")
        rev_data = conversions[conversions["revenue_usd"] > 0]["revenue_usd"]
        fig4 = px.histogram(rev_data, nbins=50, color_discrete_sequence=[COLORS["green"]])
        apply_linear_layout(fig4, height=280)
        fig4.update_layout(xaxis_title="Revenue ($)", yaxis_title="Count")
        st.plotly_chart(fig4, use_container_width=True)
    with col4:
        st.subheader("Bid Price Distribution")
        fig5 = px.histogram(impressions["bid_price_usd"], nbins=50, color_discrete_sequence=[COLORS["accent"]])
        apply_linear_layout(fig5, height=280)
        fig5.update_layout(xaxis_title="Bid Price ($)", yaxis_title="Count")
        st.plotly_chart(fig5, use_container_width=True)

    # Summary
    st.subheader("Dataset Summary")
    summary = pd.DataFrame({
        "Dataset": ["Impressions", "Clicks", "Conversions", "Campaigns"],
        "Records": [f"{len(impressions):,}", f"{len(clicks):,}", f"{len(conversions):,}", f"{len(campaigns):,}"],
        "Date Range": [
            f"{impressions['date'].min()} \u2192 {impressions['date'].max()}",
            f"{clicks['date'].min()} \u2192 {clicks['date'].max()}" if not clicks.empty else "N/A",
            f"{conversions['date'].min()} \u2192 {conversions['date'].max()}" if not conversions.empty else "N/A",
            "\u2014",
        ],
        "Null Rate": [
            f"{impressions.isnull().mean().mean():.2%}",
            f"{clicks.isnull().mean().mean():.2%}",
            f"{conversions.isnull().mean().mean():.2%}",
            f"{campaigns.isnull().mean().mean():.2%}",
        ],
    })
    st.dataframe(summary, use_container_width=True, hide_index=True)
