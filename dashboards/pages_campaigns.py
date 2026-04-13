"""
Campaign Performance page — detailed per-campaign metrics, ROAS, CPA analysis.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboards.config import COLORS, metric_card


def render(impressions, clicks, conversions, campaigns):
    st.markdown('<div class="section-header">Campaign Performance</div>', unsafe_allow_html=True)

    # Build campaign metrics table
    imp_agg = impressions.groupby("campaign_id").agg(
        impressions=("impression_id", "count"),
        spend=("bid_price_usd", "sum"),
        unique_users=("user_id", "nunique"),
    ).reset_index()

    clk_agg = clicks.groupby("campaign_id").agg(
        clicks=("click_id", "count"),
    ).reset_index()

    conv_agg = conversions.groupby("campaign_id").agg(
        conversions=("conversion_id", "count"),
        revenue=("revenue_usd", "sum"),
    ).reset_index()

    metrics = imp_agg.merge(clk_agg, on="campaign_id", how="left")
    metrics = metrics.merge(conv_agg, on="campaign_id", how="left")
    metrics = metrics.merge(campaigns[["campaign_id", "campaign_name", "channel", "status", "budget_usd"]], on="campaign_id", how="left")
    metrics = metrics.fillna(0)

    metrics["ctr"] = metrics.apply(lambda r: r["clicks"] / r["impressions"] if r["impressions"] > 0 else 0, axis=1)
    metrics["cvr"] = metrics.apply(lambda r: r["conversions"] / r["clicks"] if r["clicks"] > 0 else 0, axis=1)
    metrics["cpm"] = metrics.apply(lambda r: (r["spend"] / r["impressions"]) * 1000 if r["impressions"] > 0 else 0, axis=1)
    metrics["roas"] = metrics.apply(lambda r: r["revenue"] / r["spend"] if r["spend"] > 0 else 0, axis=1)
    metrics["cpa"] = metrics.apply(lambda r: r["spend"] / r["conversions"] if r["conversions"] > 0 else 0, axis=1)

    # Top performers
    c1, c2, c3 = st.columns(3)
    if not metrics.empty and metrics["roas"].max() > 0:
        top_roas = metrics.loc[metrics["roas"].idxmax()]
        top_conv = metrics.loc[metrics["conversions"].idxmax()]
        top_ctr_camp = metrics.loc[metrics["ctr"].idxmax()]
        with c1:
            st.markdown(metric_card("Best ROAS", f"{top_roas['roas']:.2f}x", delta=top_roas["campaign_name"], color=COLORS["success"]), unsafe_allow_html=True)
        with c2:
            st.markdown(metric_card("Most Conversions", f"{int(top_conv['conversions']):,}", delta=top_conv["campaign_name"], color=COLORS["primary"]), unsafe_allow_html=True)
        with c3:
            st.markdown(metric_card("Best CTR", f"{top_ctr_camp['ctr']:.2%}", delta=top_ctr_camp["campaign_name"], color=COLORS["info"]), unsafe_allow_html=True)

    st.markdown("---")

    # ROAS vs Spend scatter
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("ROAS vs. Spend")
        fig = px.scatter(
            metrics, x="spend", y="roas", size="conversions",
            color="channel", color_discrete_map=COLORS["channels"],
            hover_name="campaign_name",
            labels={"spend": "Total Spend ($)", "roas": "ROAS"},
        )
        fig.add_hline(y=1.0, line_dash="dash", line_color="#94A3B8", annotation_text="Breakeven")
        fig.update_layout(height=400, plot_bgcolor="white", margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Channel ROAS Comparison")
        ch_metrics = metrics.groupby("channel").agg(
            total_spend=("spend", "sum"),
            total_revenue=("revenue", "sum"),
        ).reset_index()
        ch_metrics["roas"] = ch_metrics.apply(lambda r: r["total_revenue"] / r["total_spend"] if r["total_spend"] > 0 else 0, axis=1)
        ch_metrics = ch_metrics.sort_values("roas", ascending=True)
        colors = [COLORS["channels"].get(ch, "#94A3B8") for ch in ch_metrics["channel"]]
        fig2 = go.Figure(go.Bar(
            x=ch_metrics["roas"], y=ch_metrics["channel"], orientation="h",
            marker_color=colors,
            text=[f"{v:.2f}x" for v in ch_metrics["roas"]],
            textposition="outside",
        ))
        fig2.add_vline(x=1.0, line_dash="dash", line_color="#94A3B8")
        fig2.update_layout(height=400, plot_bgcolor="white", xaxis_title="ROAS", margin=dict(l=20, r=60, t=30, b=20))
        st.plotly_chart(fig2, use_container_width=True)

    # Full campaign table
    st.subheader("Campaign Details")
    display_cols = ["campaign_name", "channel", "status", "impressions", "clicks", "conversions", "spend", "revenue", "ctr", "cvr", "roas", "cpa"]
    display = metrics[display_cols].copy()
    display["spend"] = display["spend"].apply(lambda x: f"${x:,.0f}")
    display["revenue"] = display["revenue"].apply(lambda x: f"${x:,.0f}")
    display["ctr"] = display["ctr"].apply(lambda x: f"{x:.2%}")
    display["cvr"] = display["cvr"].apply(lambda x: f"{x:.2%}")
    display["roas"] = display["roas"].apply(lambda x: f"{x:.2f}x")
    display["cpa"] = display["cpa"].apply(lambda x: f"${x:.2f}")
    display.columns = ["Campaign", "Channel", "Status", "Impr", "Clicks", "Conv", "Spend", "Revenue", "CTR", "CVR", "ROAS", "CPA"]
    st.dataframe(display, use_container_width=True, height=400)

    # Spend efficiency scatter
    st.subheader("Spend Efficiency Matrix")
    fig3 = px.scatter(
        metrics, x="cpa", y="cvr", size="spend",
        color="channel", color_discrete_map=COLORS["channels"],
        hover_name="campaign_name",
        labels={"cpa": "CPA ($)", "cvr": "Conversion Rate"},
    )
    fig3.update_layout(height=400, plot_bgcolor="white", margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig3, use_container_width=True)
    st.markdown("""
    <div class="insight-box">
        <strong>Best campaigns</strong> are in the top-left quadrant (low CPA, high CVR).
        Campaigns in the bottom-right should be reviewed for optimization or pausing.
    </div>
    """, unsafe_allow_html=True)
