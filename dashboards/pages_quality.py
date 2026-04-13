"""
Data Quality & Pipeline Health page.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboards.config import COLORS, metric_card


def render(impressions, clicks, conversions, campaigns):
    st.markdown('<div class="section-header">Data Quality & Pipeline Health</div>', unsafe_allow_html=True)

    # Overall health metrics
    c1, c2, c3, c4 = st.columns(4)

    imp_nulls = impressions.isnull().sum().sum()
    imp_dups = impressions["impression_id"].duplicated().sum()
    conv_nulls = conversions.isnull().sum().sum()
    max_ts = impressions["timestamp"].max()
    now = pd.Timestamp.now()
    # Strip timezone info to avoid naive vs aware comparison
    if hasattr(max_ts, 'tzinfo') and max_ts.tzinfo is not None:
        max_ts = max_ts.tz_localize(None)
    freshness_hours = max((now - max_ts).total_seconds() / 3600, 0)

    with c1:
        color = COLORS["success"] if imp_nulls == 0 else COLORS["danger"]
        st.markdown(metric_card("Impression Nulls", f"{imp_nulls:,}", color=color), unsafe_allow_html=True)
    with c2:
        color = COLORS["success"] if imp_dups == 0 else COLORS["warning"]
        st.markdown(metric_card("Duplicate Impressions", f"{imp_dups:,}", color=color), unsafe_allow_html=True)
    with c3:
        color = COLORS["success"] if conv_nulls == 0 else COLORS["danger"]
        st.markdown(metric_card("Conversion Nulls", f"{conv_nulls:,}", color=color), unsafe_allow_html=True)
    with c4:
        color = COLORS["success"] if freshness_hours < 48 else COLORS["warning"]
        st.markdown(metric_card("Data Freshness", f"{freshness_hours:.0f}h ago", color=color), unsafe_allow_html=True)

    st.markdown("---")

    # Completeness by column
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Impression Completeness")
        imp_complete = (1 - impressions.isnull().mean()).reset_index()
        imp_complete.columns = ["column", "completeness"]
        imp_complete["pct"] = imp_complete["completeness"] * 100
        colors = [COLORS["success"] if v >= 99 else COLORS["warning"] if v >= 95 else COLORS["danger"] for v in imp_complete["pct"]]
        fig = go.Figure(go.Bar(
            x=imp_complete["pct"], y=imp_complete["column"], orientation="h",
            marker_color=colors,
            text=[f"{v:.1f}%" for v in imp_complete["pct"]],
            textposition="inside",
        ))
        fig.add_vline(x=95, line_dash="dash", line_color="#94A3B8")
        fig.update_layout(height=350, plot_bgcolor="white", xaxis_title="Completeness %",
                          xaxis=dict(range=[80, 101]), margin=dict(l=20, r=20, t=10, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Conversion Completeness")
        conv_complete = (1 - conversions.isnull().mean()).reset_index()
        conv_complete.columns = ["column", "completeness"]
        conv_complete["pct"] = conv_complete["completeness"] * 100
        colors = [COLORS["success"] if v >= 99 else COLORS["warning"] if v >= 95 else COLORS["danger"] for v in conv_complete["pct"]]
        fig2 = go.Figure(go.Bar(
            x=conv_complete["pct"], y=conv_complete["column"], orientation="h",
            marker_color=colors,
            text=[f"{v:.1f}%" for v in conv_complete["pct"]],
            textposition="inside",
        ))
        fig2.add_vline(x=95, line_dash="dash", line_color="#94A3B8")
        fig2.update_layout(height=350, plot_bgcolor="white", xaxis_title="Completeness %",
                           xaxis=dict(range=[80, 101]), margin=dict(l=20, r=20, t=10, b=20))
        st.plotly_chart(fig2, use_container_width=True)

    # Volume over time — anomaly detection
    st.subheader("Daily Volume (Anomaly Detection)")
    daily_vol = impressions.groupby("date").size().reset_index(name="count")
    mean_vol = daily_vol["count"].mean()
    std_vol = daily_vol["count"].std()
    daily_vol["z_score"] = (daily_vol["count"] - mean_vol) / std_vol if std_vol > 0 else 0
    daily_vol["anomaly"] = daily_vol["z_score"].abs() > 2

    fig3 = go.Figure()
    normal = daily_vol[~daily_vol["anomaly"]]
    anomalies = daily_vol[daily_vol["anomaly"]]
    fig3.add_trace(go.Scatter(x=normal["date"], y=normal["count"], mode="lines+markers",
                              name="Normal", line=dict(color=COLORS["primary"]), marker=dict(size=4)))
    if not anomalies.empty:
        fig3.add_trace(go.Scatter(x=anomalies["date"], y=anomalies["count"], mode="markers",
                                  name="Anomaly", marker=dict(color=COLORS["danger"], size=10, symbol="x")))
    fig3.add_hline(y=mean_vol, line_dash="dash", line_color="#94A3B8", annotation_text="Mean")
    fig3.add_hline(y=mean_vol + 2 * std_vol, line_dash="dot", line_color=COLORS["warning"], annotation_text="+2σ")
    fig3.add_hline(y=mean_vol - 2 * std_vol, line_dash="dot", line_color=COLORS["warning"], annotation_text="-2σ")
    fig3.update_layout(height=350, plot_bgcolor="white", yaxis_title="Daily Impressions",
                       margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig3, use_container_width=True)

    # Revenue distribution
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Revenue Distribution")
        rev_data = conversions[conversions["revenue_usd"] > 0]["revenue_usd"]
        fig4 = px.histogram(rev_data, nbins=50, color_discrete_sequence=[COLORS["success"]])
        fig4.update_layout(height=300, plot_bgcolor="white", xaxis_title="Revenue ($)", yaxis_title="Count",
                           margin=dict(l=20, r=20, t=10, b=20))
        st.plotly_chart(fig4, use_container_width=True)

    with col4:
        st.subheader("Bid Price Distribution")
        fig5 = px.histogram(impressions["bid_price_usd"], nbins=50, color_discrete_sequence=[COLORS["primary"]])
        fig5.update_layout(height=300, plot_bgcolor="white", xaxis_title="Bid Price ($)", yaxis_title="Count",
                           margin=dict(l=20, r=20, t=10, b=20))
        st.plotly_chart(fig5, use_container_width=True)

    # Data summary table
    st.subheader("Dataset Summary")
    summary = pd.DataFrame({
        "Dataset": ["Impressions", "Clicks", "Conversions", "Campaigns"],
        "Records": [f"{len(impressions):,}", f"{len(clicks):,}", f"{len(conversions):,}", f"{len(campaigns):,}"],
        "Date Range": [
            f"{impressions['date'].min()} → {impressions['date'].max()}",
            f"{clicks['date'].min()} → {clicks['date'].max()}",
            f"{conversions['date'].min()} → {conversions['date'].max()}",
            "—",
        ],
        "Null Rate": [
            f"{impressions.isnull().mean().mean():.2%}",
            f"{clicks.isnull().mean().mean():.2%}",
            f"{conversions.isnull().mean().mean():.2%}",
            f"{campaigns.isnull().mean().mean():.2%}",
        ],
    })
    st.dataframe(summary, use_container_width=True, hide_index=True)
