"""Channel & Journey Analysis — funnel, trends, patterns (Linear dark theme)."""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboards.config import COLORS, metric_card, apply_linear_layout


def render(impressions, clicks, conversions, campaigns):
    st.markdown('<div class="section-header">Channel & Journey Analysis</div>', unsafe_allow_html=True)

    channels = sorted(impressions["channel"].unique())

    imp_by_ch = impressions.groupby("channel").agg(
        impressions=("impression_id", "count"), spend=("bid_price_usd", "sum"),
    )
    clk_by_ch = clicks.groupby("channel").size().rename("clicks")
    conv_by_ch = conversions.groupby("channel").agg(
        conversions=("conversion_id", "count"), revenue=("revenue_usd", "sum"),
    )
    funnel_df = imp_by_ch.join(clk_by_ch, how="left").join(conv_by_ch, how="left").fillna(0).reset_index()
    funnel_df["ctr"] = (funnel_df["clicks"] / funnel_df["impressions"]).fillna(0)
    funnel_df["cvr"] = (funnel_df["conversions"] / funnel_df["clicks"]).fillna(0)
    funnel_df["roas"] = (funnel_df["revenue"] / funnel_df["spend"]).fillna(0)

    selected_channel = st.selectbox("Select Channel", channels)
    ch_row = funnel_df[funnel_df["channel"] == selected_channel].iloc[0]
    color = COLORS["channels"].get(selected_channel, COLORS["accent"])

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(metric_card("Impressions", f"{int(ch_row['impressions']):,}", accent_color=color), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card("Clicks", f"{int(ch_row['clicks']):,}", accent_color=color), unsafe_allow_html=True)
    with c3:
        st.markdown(metric_card("Conversions", f"{int(ch_row['conversions']):,}", accent_color=color), unsafe_allow_html=True)
    with c4:
        st.markdown(metric_card("CTR", f"{ch_row['ctr']:.2%}", accent_color=color), unsafe_allow_html=True)
    with c5:
        st.markdown(metric_card("ROAS", f"{ch_row['roas']:.2f}x", accent_color=color), unsafe_allow_html=True)

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Channel Funnel")
        fig = go.Figure(go.Funnel(
            y=["Impressions", "Clicks", "Conversions"],
            x=[ch_row["impressions"], ch_row["clicks"], ch_row["conversions"]],
            marker=dict(color=[color, color, color]),
            textinfo="value+percent previous",
            textfont=dict(color="#f7f8f8"),
        ))
        apply_linear_layout(fig, height=340)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("All Channels CTR & CVR")
        fig2 = go.Figure()
        for _, row in funnel_df.iterrows():
            fig2.add_trace(go.Bar(
                name=row["channel"], x=["CTR", "CVR"],
                y=[row["ctr"] * 100, row["cvr"] * 100],
                marker_color=COLORS["channels"].get(row["channel"], "#8a8f98"),
                marker_line_width=0,
            ))
        fig2.update_layout(barmode="group", yaxis_title="Rate (%)", legend=dict(orientation="h", y=-0.18))
        apply_linear_layout(fig2, height=340)
        st.plotly_chart(fig2, use_container_width=True)

    # Daily trends by channel
    st.subheader("Daily Trends by Channel")
    metric_choice = st.radio("Metric", ["Impressions", "Spend", "Conversions"], horizontal=True)
    if metric_choice == "Impressions":
        daily_ch = impressions.groupby(["date", "channel"]).size().reset_index(name="value")
    elif metric_choice == "Spend":
        daily_ch = impressions.groupby(["date", "channel"])["bid_price_usd"].sum().reset_index(name="value")
    else:
        daily_ch = conversions.groupby(["date", "channel"]).size().reset_index(name="value")

    fig3 = px.area(daily_ch, x="date", y="value", color="channel",
                   color_discrete_map=COLORS["channels"],
                   labels={"value": metric_choice, "date": ""})
    apply_linear_layout(fig3, height=380)
    st.plotly_chart(fig3, use_container_width=True)

    # Hourly pattern
    st.subheader("Hourly Activity Pattern")
    imp_hour = impressions.copy()
    imp_hour["hour"] = imp_hour["timestamp"].dt.hour
    hourly = imp_hour.groupby(["hour", "channel"]).size().reset_index(name="count")
    fig4 = px.line(hourly, x="hour", y="count", color="channel",
                   color_discrete_map=COLORS["channels"],
                   labels={"count": "Impressions", "hour": "Hour of Day"})
    apply_linear_layout(fig4, height=320)
    st.plotly_chart(fig4, use_container_width=True)

    # Conversion types
    st.subheader("Conversion Types by Channel")
    conv_types = conversions.groupby(["channel", "conversion_type"]).size().reset_index(name="count")
    fig5 = px.bar(conv_types, x="channel", y="count", color="conversion_type",
                  color_discrete_sequence=[COLORS["accent"], COLORS["green"], COLORS["amber"]],
                  barmode="stack")
    apply_linear_layout(fig5, height=340)
    st.plotly_chart(fig5, use_container_width=True)
