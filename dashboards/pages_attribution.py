"""
Attribution Analysis page — model comparison, channel credit, transition matrix.
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import numpy as np

from dashboards.config import COLORS, metric_card


def render(impressions, conversions, attribution_df):
    st.markdown('<div class="section-header">Attribution Model Comparison</div>', unsafe_allow_html=True)

    if attribution_df.empty:
        st.warning("No attribution data available. Check that data has been generated.")
        return

    models = attribution_df["model"].unique().tolist()
    channels = sorted(attribution_df["channel"].dropna().unique().tolist())

    # Model taxonomy
    st.markdown("""
    <div class="insight-box">
        <strong>Heuristic models</strong> (last-touch, first-touch, linear, time-decay, position-based)
        use fixed rules. <strong>Data-driven models</strong> (Markov chain, Shapley value) learn from
        actual user journey data — they are statistically fairer and capture cross-channel effects
        that heuristic models miss entirely.
    </div>
    """, unsafe_allow_html=True)

    # Grouped bar chart: all models side by side
    st.subheader("Credit Allocation by Model")
    model_order = ["last_touch", "first_touch", "linear", "time_decay", "position_based", "markov_chain", "shapley_value"]
    model_labels = {
        "last_touch": "Last Touch", "first_touch": "First Touch", "linear": "Linear",
        "time_decay": "Time Decay", "position_based": "Position Based",
        "markov_chain": "Markov Chain", "shapley_value": "Shapley Value",
    }
    attribution_df = attribution_df.copy()
    attribution_df["model_label"] = attribution_df["model"].map(model_labels)
    attribution_df["credit_pct"] = attribution_df["credit"] * 100

    fig = px.bar(
        attribution_df, x="channel", y="credit_pct", color="model_label",
        barmode="group",
        color_discrete_sequence=[
            "#94A3B8", "#CBD5E1", "#A5B4FC", "#818CF8",
            "#C084FC", COLORS["primary"], COLORS["danger"],
        ],
        labels={"credit_pct": "Credit (%)", "channel": "Channel", "model_label": "Model"},
    )
    fig.update_layout(
        height=450, plot_bgcolor="white",
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", y=-0.15),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Heatmap: models x channels
    st.subheader("Attribution Heatmap")
    pivot = attribution_df.pivot_table(index="model_label", columns="channel", values="credit_pct", aggfunc="mean").fillna(0)
    fig2 = px.imshow(
        pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        color_continuous_scale="Purples", aspect="auto",
        labels=dict(color="Credit (%)"),
    )
    fig2.update_layout(height=350, margin=dict(l=20, r=20, t=30, b=20))
    st.plotly_chart(fig2, use_container_width=True)

    # Side-by-side: Heuristic vs Data-driven
    st.subheader("Heuristic vs. Data-Driven Attribution")
    col1, col2 = st.columns(2)

    heuristic_models = ["last_touch", "first_touch", "linear", "time_decay", "position_based"]
    data_driven_models = ["markov_chain", "shapley_value"]

    with col1:
        st.markdown("**Heuristic Models (avg)**")
        heuristic = attribution_df[attribution_df["model"].isin(heuristic_models)]
        if not heuristic.empty:
            avg_heuristic = heuristic.groupby("channel")["credit_pct"].mean().reset_index()
            fig3 = px.pie(avg_heuristic, values="credit_pct", names="channel", hole=0.4,
                          color="channel", color_discrete_map=COLORS["channels"])
            fig3.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig3, use_container_width=True)

    with col2:
        st.markdown("**Data-Driven Models (avg)**")
        data_driven = attribution_df[attribution_df["model"].isin(data_driven_models)]
        if not data_driven.empty:
            avg_dd = data_driven.groupby("channel")["credit_pct"].mean().reset_index()
            fig4 = px.pie(avg_dd, values="credit_pct", names="channel", hole=0.4,
                          color="channel", color_discrete_map=COLORS["channels"])
            fig4.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig4, use_container_width=True)

    # Divergence analysis
    st.subheader("Model Divergence (Where Models Disagree)")
    if not heuristic.empty and not data_driven.empty:
        h_avg = heuristic.groupby("channel")["credit_pct"].mean()
        d_avg = data_driven.groupby("channel")["credit_pct"].mean()
        diff = (d_avg - h_avg).dropna().reset_index()
        diff.columns = ["channel", "divergence"]
        diff = diff.sort_values("divergence")
        colors = [COLORS["success"] if v > 0 else COLORS["danger"] for v in diff["divergence"]]
        fig5 = go.Figure(go.Bar(
            x=diff["divergence"], y=diff["channel"], orientation="h",
            marker_color=colors,
            text=[f"{v:+.1f}%" for v in diff["divergence"]],
            textposition="outside",
        ))
        fig5.update_layout(
            height=300, plot_bgcolor="white",
            xaxis_title="Data-Driven minus Heuristic (pp)",
            margin=dict(l=20, r=60, t=20, b=20),
        )
        st.plotly_chart(fig5, use_container_width=True)
        st.markdown("""
        <div class="insight-box">
            <strong>Green bars</strong> = data-driven models give MORE credit than heuristic models.
            <strong>Red bars</strong> = data-driven models give LESS credit. Large divergences
            indicate channels where traditional attribution is misleading your spend decisions.
        </div>
        """, unsafe_allow_html=True)
