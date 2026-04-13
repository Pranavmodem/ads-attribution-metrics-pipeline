"""
Dashboard design system — Linear-inspired dark-mode-first aesthetic.

Color tokens, CSS, and reusable components following the Linear design language:
near-black canvas, semi-transparent white borders, indigo-violet accent,
Inter font family, luminance-based depth.
"""

# ─── Color Tokens (Linear Design System) ────────────────────────
COLORS = {
    # Backgrounds
    "bg_base": "#08090a",
    "bg_panel": "#0f1011",
    "bg_surface": "#191a1b",
    "bg_elevated": "#28282c",
    # Text
    "text_primary": "#f7f8f8",
    "text_secondary": "#d0d6e0",
    "text_tertiary": "#8a8f98",
    "text_quaternary": "#62666d",
    # Brand
    "brand": "#5e6ad2",
    "accent": "#7170ff",
    "accent_hover": "#828fff",
    # Status
    "green": "#10b981",
    "red": "#ef4444",
    "amber": "#f59e0b",
    "blue": "#3b82f6",
    # Borders
    "border_subtle": "rgba(255,255,255,0.05)",
    "border_standard": "rgba(255,255,255,0.08)",
    "border_solid": "#23252a",
    # Channel colors (muted to fit dark theme)
    "channels": {
        "Paid Search": "#7170ff",
        "Social": "#c084fc",
        "Display": "#f59e0b",
        "Video": "#ef4444",
        "Email": "#10b981",
        "Native": "#828fff",
        "Affiliate": "#38bdf8",
    },
}

# Chart color sequence for Plotly
CHART_COLORS = ["#7170ff", "#c084fc", "#f59e0b", "#ef4444", "#10b981", "#828fff", "#38bdf8"]

# ─── Plotly Dark Template ────────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", color="#d0d6e0", size=12),
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        zerolinecolor="rgba(255,255,255,0.05)",
        tickfont=dict(color="#8a8f98"),
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        zerolinecolor="rgba(255,255,255,0.05)",
        tickfont=dict(color="#8a8f98"),
    ),
    legend=dict(
        font=dict(color="#d0d6e0", size=11),
        bgcolor="rgba(0,0,0,0)",
    ),
    margin=dict(l=20, r=20, t=30, b=20),
    hoverlabel=dict(bgcolor="#191a1b", font_color="#f7f8f8", bordercolor="#23252a"),
)


# ─── Custom CSS (Linear DESIGN.md strict) ───────────────────────
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

    /* ── Global: Inter + cv01/ss03 + #08090a canvas ── */
    *, *::before, *::after {
        font-feature-settings: "cv01", "ss03";
    }
    .stApp {
        font-family: 'Inter', SF Pro Display, -apple-system, system-ui, Segoe UI, Roboto, sans-serif;
        background-color: #08090a;
        color: #f7f8f8;
        font-weight: 400;
        font-size: 15px;
        line-height: 1.6;
        letter-spacing: -0.165px;
    }
    .stApp > header { background-color: #08090a; }
    .main .block-container { padding-top: 2rem; max-width: 1200px; }

    /* ── Sidebar: #0f1011 panel ── */
    section[data-testid="stSidebar"] {
        background-color: #0f1011;
        border-right: 1px solid rgba(255,255,255,0.05);
    }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 1.5rem; }
    section[data-testid="stSidebar"] * { color: #8a8f98 !important; }

    /* Nav: 13px weight 510 (approx 500), pill hover */
    section[data-testid="stSidebar"] .stRadio > div {
        gap: 2px !important;
        background: transparent !important;
        border: none !important;
    }
    section[data-testid="stSidebar"] .stRadio > div > label {
        color: #d0d6e0 !important;
        font-size: 13px;
        font-weight: 510;
        letter-spacing: -0.13px;
        line-height: 1.5;
        padding: 7px 12px !important;
        border-radius: 6px;
        transition: all 0.12s ease;
        cursor: pointer;
        border: none !important;
        background: transparent !important;
    }
    section[data-testid="stSidebar"] .stRadio > div > label:hover {
        color: #f7f8f8 !important;
        background: rgba(255,255,255,0.04) !important;
    }
    section[data-testid="stSidebar"] .stRadio > div > label[data-checked="true"] {
        color: #f7f8f8 !important;
        background: rgba(255,255,255,0.05) !important;
    }
    section[data-testid="stSidebar"] .stRadio > div > label > div:first-child {
        display: none !important;
    }

    /* ── Typography hierarchy (DESIGN.md §3) ── */
    h1, h2, h3, h4 { color: #f7f8f8 !important; font-feature-settings: "cv01", "ss03"; }
    h1 { font-size: 32px; font-weight: 400; line-height: 1.13; letter-spacing: -0.704px; }
    h2 { font-size: 24px; font-weight: 400; line-height: 1.33; letter-spacing: -0.288px; }
    h3 { font-size: 20px; font-weight: 590; line-height: 1.33; letter-spacing: -0.24px; }

    /* Body text */
    p, span, li, div { color: #d0d6e0; font-weight: 400; }

    /* ── Metric Cards: Level 2 surface ── */
    .linear-card {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 8px;
        padding: 20px 24px;
        transition: background 0.15s ease;
    }
    .linear-card:hover { background: rgba(255,255,255,0.04); }
    .linear-card .label {
        font-size: 10px;
        color: #62666d;
        font-weight: 510;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    .linear-card .value {
        font-size: 28px;
        font-weight: 510;
        color: #f7f8f8;
        letter-spacing: -0.704px;
        line-height: 1.13;
    }
    .linear-card .delta {
        font-size: 11px;
        margin-top: 8px;
        font-weight: 510;
    }
    .delta-positive { color: #10b981; }
    .delta-negative { color: #ef4444; }

    /* ── Section Headers: Heading 2 ── */
    .section-header {
        font-size: 24px;
        font-weight: 400;
        color: #f7f8f8;
        letter-spacing: -0.288px;
        line-height: 1.33;
        margin: 32px 0 20px 0;
        padding-bottom: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }

    /* ── Insight Box ── */
    .insight-box {
        background: rgba(94,106,210,0.06);
        border-radius: 8px;
        padding: 16px 20px;
        border-left: 3px solid #5e6ad2;
        margin: 16px 0;
        font-size: 14px;
        font-weight: 400;
        color: #d0d6e0;
        line-height: 1.6;
        letter-spacing: -0.182px;
    }
    .insight-box strong { color: #f7f8f8; font-weight: 590; }

    /* ── Pill Badges ── */
    .pill {
        display: inline-block;
        padding: 0px 10px 0px 5px;
        border-radius: 9999px;
        font-size: 12px;
        font-weight: 510;
        border: 1px solid #23252a;
        color: #d0d6e0;
        background: transparent;
    }

    /* ── Tables: Level 2 surface ── */
    .stDataFrame { border-radius: 8px; overflow: hidden; }
    .stDataFrame table { background: rgba(255,255,255,0.02); }
    .stDataFrame th {
        background: rgba(255,255,255,0.04) !important;
        color: #62666d !important;
        font-weight: 510;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .stDataFrame td {
        color: #d0d6e0 !important;
        font-size: 13px;
        font-weight: 400;
        border-color: rgba(255,255,255,0.05) !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .stTabs [data-baseweb="tab"] {
        color: #8a8f98;
        font-weight: 510;
        font-size: 13px;
        letter-spacing: -0.13px;
    }
    .stTabs [aria-selected="true"] {
        color: #f7f8f8 !important;
        border-bottom-color: #5e6ad2 !important;
    }

    /* ── Inputs: ghost style (DESIGN.md §4) ── */
    .stSelectbox > div > div {
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 6px;
        color: #d0d6e0;
        font-size: 13px;
        font-weight: 510;
    }
    .stSlider > div > div { color: #8a8f98; }

    /* ── Buttons: ghost default (DESIGN.md §4) ── */
    .stButton button {
        background: rgba(255,255,255,0.02);
        color: #e2e4e7;
        border: 1px solid rgb(36, 40, 44);
        border-radius: 6px;
        font-weight: 510;
        font-size: 12px;
        letter-spacing: normal;
        transition: background 0.12s ease;
        outline: none;
    }
    .stButton button:hover {
        background: rgba(255,255,255,0.05);
        color: #f7f8f8;
    }
    .stButton button:focus {
        box-shadow: rgba(0,0,0,0.1) 0px 4px 12px;
    }

    /* ── Dividers: border-subtle ── */
    hr { border-color: rgba(255,255,255,0.05) !important; }

    /* ── Spinner: brand accent ── */
    .stSpinner > div { color: #7170ff !important; }

    /* ── Scrollbar: subtle ── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #08090a; }
    ::-webkit-scrollbar-thumb { background: #28282c; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #34343a; }
</style>
"""


def metric_card(label, value, delta=None, delta_positive=True, accent_color=None):
    """Render a Linear-style metric card."""
    from html import escape
    label = escape(str(label))
    value = escape(str(value))
    delta_html = ""
    if delta is not None:
        cls = "delta-positive" if delta_positive else "delta-negative"
        arrow = "&#8593;" if delta_positive else "&#8595;"
        delta_html = f'<div class="delta {cls}">{arrow} {escape(str(delta))}</div>'
    accent = ""
    if accent_color:
        accent = f' style="border-left: 3px solid {accent_color};"'
    return f"""
    <div class="linear-card"{accent}>
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        {delta_html}
    </div>
    """


def apply_linear_layout(fig, height=350, **kwargs):
    """Apply Linear dark theme to a Plotly figure."""
    layout = {**PLOTLY_LAYOUT, "height": height, **kwargs}
    fig.update_layout(**layout)
    return fig
