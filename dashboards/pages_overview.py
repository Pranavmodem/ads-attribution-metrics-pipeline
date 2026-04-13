"""Executive Overview — KPI cards, trends, breakdowns (Linear dark theme)."""
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from dashboards.config import COLORS, CHART_COLORS, metric_card, apply_linear_layout


def render(impressions, clicks, conversions, campaigns):
    st.markdown('<div class="section-header">Executive Overview</div>', unsafe_allow_html=True)

    total_imp = len(impressions)
    total_clk = len(clicks)
    total_conv = len(conversions)
    total_spend = impressions["bid_price_usd"].sum()
    total_rev = conversions["revenue_usd"].sum()
    ctr = total_clk / total_imp if total_imp else 0
    cvr = total_conv / total_clk if total_clk else 0
    roas = total_rev / total_spend if total_spend else 0
    cpa = total_spend / total_conv if total_conv else 0

    # KPI Row 1
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(metric_card("Impressions", f"{total_imp:,.0f}", accent_color=COLORS["accent"]), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Clicks", f"{total_clk:,.0f}", accent_color=COLORS["blue"]), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Conversions", f"{total_conv:,.0f}", accent_color=COLORS["green"]), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("Revenue", f"${total_rev:,.0f}", accent_color=COLORS["brand"]), unsafe_allow_html=True)

    # KPI Row 2
    c5, c6, c7, c8 = st.columns(4)
    with c5:
        st.markdown(metric_card("CTR", f"{ctr:.2%}"), unsafe_allow_html=True)
    with c6:
        st.markdown(metric_card("CVR", f"{cvr:.2%}"), unsafe_allow_html=True)
    with c7:
        st.markdown(metric_card("ROAS", f"{roas:.2f}x"), unsafe_allow_html=True)
    with c8:
        st.markdown(metric_card("CPA", f"${cpa:.2f}"), unsafe_allow_html=True)

    st.markdown("---")

    # Daily trends
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Daily Impressions & Clicks")
        daily_imp = impressions.groupby("date").size().reset_index(name="impressions")
        daily_clk = clicks.groupby("date").size().reset_index(name="clicks")
        daily = daily_imp.merge(daily_clk, on="date", how="left").fillna(0)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["impressions"], name="Impressions",
            fill="tozeroy", line=dict(color=COLORS["accent"], width=1.5),
            fillcolor="rgba(113,112,255,0.08)",
        ))
        fig.add_trace(go.Scatter(
            x=daily["date"], y=daily["clicks"], name="Clicks",
            fill="tozeroy", line=dict(color=COLORS["green"], width=1.5),
            fillcolor="rgba(16,185,129,0.08)", yaxis="y2",
        ))
        fig.update_layout(
            yaxis2=dict(overlaying="y", side="right", gridcolor="rgba(255,255,255,0.05)",
                        tickfont=dict(color="#8a8f98"), showgrid=False),
            legend=dict(orientation="h", y=1.12),
        )
        apply_linear_layout(fig, height=340)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Daily Revenue & Conversions")
        daily_conv = conversions.groupby("date").agg(
            conversions=("conversion_id", "count"), revenue=("revenue_usd", "sum"),
        ).reset_index()
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=daily_conv["date"], y=daily_conv["revenue"], name="Revenue ($)",
            marker_color="rgba(94,106,210,0.5)", marker_line_width=0,
        ))
        fig2.add_trace(go.Scatter(
            x=daily_conv["date"], y=daily_conv["conversions"], name="Conversions",
            line=dict(color=COLORS["green"], width=2), yaxis="y2",
        ))
        fig2.update_layout(
            yaxis2=dict(overlaying="y", side="right", gridcolor="rgba(255,255,255,0.05)",
                        tickfont=dict(color="#8a8f98"), showgrid=False),
            legend=dict(orientation="h", y=1.12),
        )
        apply_linear_layout(fig2, height=340)
        st.plotly_chart(fig2, use_container_width=True)

    # Channel + Device
    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Impressions by Channel")
        ch_data = impressions.groupby("channel").size().reset_index(name="impressions").sort_values("impressions", ascending=True)
        colors = [COLORS["channels"].get(ch, "#8a8f98") for ch in ch_data["channel"]]
        fig3 = go.Figure(go.Bar(
            y=ch_data["channel"], x=ch_data["impressions"], orientation="h",
            marker_color=colors, marker_line_width=0,
        ))
        apply_linear_layout(fig3, height=320)
        fig3.update_layout(showlegend=False)
        st.plotly_chart(fig3, use_container_width=True)

    with col_b:
        st.subheader("Device & Geo Split")
        tab1, tab2 = st.tabs(["Device", "Geography"])
        with tab1:
            device_data = impressions["device_type"].value_counts().reset_index()
            device_data.columns = ["device", "count"]
            fig4 = px.pie(device_data, values="count", names="device", hole=0.5,
                          color_discrete_sequence=CHART_COLORS)
            apply_linear_layout(fig4, height=300)
            st.plotly_chart(fig4, use_container_width=True)
        with tab2:
            geo_data = impressions["geo_country"].value_counts().reset_index()
            geo_data.columns = ["country", "count"]
            fig5 = go.Figure(go.Bar(
                x=geo_data["country"], y=geo_data["count"],
                marker_color=COLORS["accent"], marker_line_width=0, opacity=0.7,
            ))
            apply_linear_layout(fig5, height=300)
            st.plotly_chart(fig5, use_container_width=True)
