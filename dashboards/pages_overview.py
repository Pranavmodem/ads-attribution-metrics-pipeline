"""
Executive Overview page — KPI cards, trends, top-level metrics.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboards.config import COLORS, metric_card


def render(impressions, clicks, conversions, campaigns):
    st.markdown('<div class="section-header">Executive Overview</div>', unsafe_allow_html=True)

    total_impressions = len(impressions)
    total_clicks = len(clicks)
    total_conversions = len(conversions)
    total_spend = impressions["bid_price_usd"].sum()
    total_revenue = conversions["revenue_usd"].sum()
    ctr = total_clicks / total_impressions if total_impressions else 0
    cvr = total_conversions / total_clicks if total_clicks else 0
    roas = total_revenue / total_spend if total_spend else 0
    cpa = total_spend / total_conversions if total_conversions else 0

    # KPI Row 1
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(metric_card("Total Impressions", f"{total_impressions:,.0f}", color=COLORS["primary"]), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Total Clicks", f"{total_clicks:,.0f}", color=COLORS["info"]), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Total Conversions", f"{total_conversions:,.0f}", color=COLORS["success"]), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("Total Revenue", f"${total_revenue:,.0f}", color=COLORS["secondary"]), unsafe_allow_html=True)

    # KPI Row 2
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(metric_card("CTR", f"{ctr:.2%}", color=COLORS["info"]), unsafe_allow_html=True)
    with c6:
        st.markdown(metric_card("CVR", f"{cvr:.2%}", color=COLORS["success"]), unsafe_allow_html=True)
    with c7:
        st.markdown(metric_card("ROAS", f"{roas:.2f}x", color=COLORS["warning"]), unsafe_allow_html=True)
    with c8:
        st.markdown(metric_card("CPA", f"${cpa:.2f}", color=COLORS["danger"]), unsafe_allow_html=True)

    st.markdown("---")

    # Daily trends
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Daily Impressions & Clicks")
        daily_imp = impressions.groupby("date").size().reset_index(name="impressions")
        daily_clk = clicks.groupby("date").size().reset_index(name="clicks")
        daily = daily_imp.merge(daily_clk, on="date", how="left").fillna(0)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily["date"], y=daily["impressions"], name="Impressions", fill="tozeroy", line=dict(color=COLORS["primary"])))
        fig.add_trace(go.Scatter(x=daily["date"], y=daily["clicks"], name="Clicks", fill="tozeroy", line=dict(color=COLORS["info"]), yaxis="y2"))
        fig.update_layout(
            yaxis=dict(title="Impressions", showgrid=False),
            yaxis2=dict(title="Clicks", overlaying="y", side="right", showgrid=False),
            height=350, margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", y=1.1),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("Daily Revenue & Conversions")
        daily_conv = conversions.groupby("date").agg(
            conversions=("conversion_id", "count"),
            revenue=("revenue_usd", "sum"),
        ).reset_index()
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=daily_conv["date"], y=daily_conv["revenue"], name="Revenue ($)", marker_color=COLORS["success"], opacity=0.7))
        fig2.add_trace(go.Scatter(x=daily_conv["date"], y=daily_conv["conversions"], name="Conversions", line=dict(color=COLORS["danger"], width=2), yaxis="y2"))
        fig2.update_layout(
            yaxis=dict(title="Revenue ($)", showgrid=False),
            yaxis2=dict(title="Conversions", overlaying="y", side="right", showgrid=False),
            height=350, margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", y=1.1),
            plot_bgcolor="white",
        )
        st.plotly_chart(fig2, use_container_width=True)

    # Channel + Device breakdown
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Impressions by Channel")
        ch_data = impressions.groupby("channel").agg(
            impressions=("impression_id", "count"),
            spend=("bid_price_usd", "sum"),
        ).reset_index().sort_values("impressions", ascending=True)
        channel_colors = [COLORS["channels"].get(ch, "#94A3B8") for ch in ch_data["channel"]]
        fig3 = px.bar(ch_data, y="channel", x="impressions", orientation="h", color="channel",
                      color_discrete_map=COLORS["channels"])
        fig3.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20), showlegend=False, plot_bgcolor="white")
        st.plotly_chart(fig3, use_container_width=True)

    with col_b:
        st.subheader("Device & Geo Split")
        tab1, tab2 = st.tabs(["Device", "Geography"])
        with tab1:
            device_data = impressions["device_type"].value_counts().reset_index()
            device_data.columns = ["device", "count"]
            fig4 = px.pie(device_data, values="count", names="device", hole=0.45,
                          color_discrete_sequence=[COLORS["primary"], COLORS["info"], COLORS["success"], COLORS["warning"]])
            fig4.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig4, use_container_width=True)
        with tab2:
            geo_data = impressions["geo_country"].value_counts().reset_index()
            geo_data.columns = ["country", "count"]
            fig5 = px.bar(geo_data, x="country", y="count", color="count",
                          color_continuous_scale=["#C7D2FE", COLORS["primary"]])
            fig5.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), plot_bgcolor="white", showlegend=False)
            st.plotly_chart(fig5, use_container_width=True)
