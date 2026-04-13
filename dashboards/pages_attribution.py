"""Attribution Analysis — model comparison, heatmap, divergence (Linear dark theme)."""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboards.config import COLORS, apply_linear_layout


def render(impressions, conversions, attribution_df):
    st.markdown('<div class="section-header">Attribution Model Comparison</div>', unsafe_allow_html=True)

    if attribution_df.empty:
        st.warning("No attribution data available.")
        return

    st.markdown("""
    <div class="insight-box">
        <strong>Heuristic models</strong> (last-touch, first-touch, linear, time-decay, position-based)
        use fixed rules. <strong>Data-driven models</strong> (Markov chain, Shapley value) learn from
        actual user journey data &mdash; they capture cross-channel effects that heuristic models miss entirely.
    </div>
    """, unsafe_allow_html=True)

    model_labels = {
        "last_touch": "Last Touch", "first_touch": "First Touch", "linear": "Linear",
        "time_decay": "Time Decay", "position_based": "Position Based",
        "markov_chain": "Markov Chain", "shapley_value": "Shapley Value",
    }
    model_order = ["Last Touch", "First Touch", "Linear", "Time Decay", "Position Based", "Markov Chain", "Shapley Value"]
    df = attribution_df.copy()
    df["model_label"] = df["model"].map(model_labels)
    df["credit_pct"] = df["credit"] * 100

    # Grouped bar chart
    st.subheader("Credit Allocation by Model")
    model_colors = ["#34343a", "#3e3e44", "#62666d", "#8a8f98", "#c084fc", "#7170ff", "#ef4444"]
    fig = px.bar(
        df, x="channel", y="credit_pct", color="model_label",
        barmode="group", color_discrete_sequence=model_colors,
        category_orders={"model_label": model_order},
        labels={"credit_pct": "Credit (%)", "channel": "", "model_label": "Model"},
    )
    apply_linear_layout(fig, height=420)
    fig.update_layout(legend=dict(orientation="h", y=-0.18))
    st.plotly_chart(fig, use_container_width=True)

    # Heatmap
    st.subheader("Attribution Heatmap")
    pivot = df.pivot_table(index="model_label", columns="channel", values="credit_pct", aggfunc="mean").fillna(0)
    ordered = [m for m in model_order if m in pivot.index]
    pivot = pivot.reindex(ordered)
    fig2 = px.imshow(
        pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        color_continuous_scale=[[0, "#08090a"], [0.5, "#5e6ad2"], [1, "#828fff"]],
        aspect="auto", labels=dict(color="Credit (%)"),
    )
    apply_linear_layout(fig2, height=320)
    st.plotly_chart(fig2, use_container_width=True)

    # Heuristic vs Data-driven
    st.subheader("Heuristic vs. Data-Driven")
    heuristic_models = ["last_touch", "first_touch", "linear", "time_decay", "position_based"]
    data_driven_models = ["markov_chain", "shapley_value"]

    col1, col2 = st.columns(2)
    heuristic = df[df["model"].isin(heuristic_models)]
    data_driven = df[df["model"].isin(data_driven_models)]

    with col1:
        st.markdown("**Heuristic Models (avg)**")
        if not heuristic.empty:
            avg_h = heuristic.groupby("channel")["credit_pct"].mean().reset_index()
            fig3 = px.pie(avg_h, values="credit_pct", names="channel", hole=0.5,
                          color="channel", color_discrete_map=COLORS["channels"])
            apply_linear_layout(fig3, height=280)
            st.plotly_chart(fig3, use_container_width=True)

    with col2:
        st.markdown("**Data-Driven Models (avg)**")
        if not data_driven.empty:
            avg_d = data_driven.groupby("channel")["credit_pct"].mean().reset_index()
            fig4 = px.pie(avg_d, values="credit_pct", names="channel", hole=0.5,
                          color="channel", color_discrete_map=COLORS["channels"])
            apply_linear_layout(fig4, height=280)
            st.plotly_chart(fig4, use_container_width=True)

    # Divergence
    st.subheader("Model Divergence")
    if not heuristic.empty and not data_driven.empty:
        h_avg = heuristic.groupby("channel")["credit_pct"].mean()
        d_avg = data_driven.groupby("channel")["credit_pct"].mean()
        diff = (d_avg - h_avg).dropna().reset_index()
        diff.columns = ["channel", "divergence"]
        diff = diff.sort_values("divergence")
        colors = [COLORS["green"] if v > 0 else COLORS["red"] for v in diff["divergence"]]
        fig5 = go.Figure(go.Bar(
            x=diff["divergence"], y=diff["channel"], orientation="h",
            marker_color=colors, marker_line_width=0,
            text=[f"{v:+.1f}%" for v in diff["divergence"]], textposition="outside",
            textfont=dict(color="#d0d6e0", size=11),
        ))
        apply_linear_layout(fig5, height=280)
        fig5.update_layout(xaxis_title="Data-Driven minus Heuristic (pp)")
        st.plotly_chart(fig5, use_container_width=True)
        st.markdown("""
        <div class="insight-box">
            <strong style="color:#10b981;">Green</strong> = data-driven gives MORE credit.
            <strong style="color:#ef4444;">Red</strong> = data-driven gives LESS credit.
            Large divergences indicate where traditional attribution misleads spend decisions.
        </div>
        """, unsafe_allow_html=True)
