"""
Streamlit dashboard configuration and shared styles.
"""

# Color palette
COLORS = {
    "primary": "#4F46E5",
    "secondary": "#7C3AED",
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "info": "#3B82F6",
    "dark": "#1E293B",
    "light": "#F8FAFC",
    "channels": {
        "Paid Search": "#4F46E5",
        "Social": "#EC4899",
        "Display": "#F59E0B",
        "Video": "#EF4444",
        "Email": "#10B981",
        "Native": "#8B5CF6",
        "Affiliate": "#06B6D4",
    },
}

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    .stApp { font-family: 'Inter', sans-serif; }
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 20px 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06);
        border-left: 4px solid;
        margin-bottom: 8px;
    }
    .metric-card .label { font-size: 13px; color: #64748B; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
    .metric-card .value { font-size: 28px; font-weight: 700; color: #1E293B; }
    .metric-card .delta { font-size: 13px; margin-top: 4px; }
    .delta-positive { color: #10B981; }
    .delta-negative { color: #EF4444; }
    .section-header { font-size: 20px; font-weight: 700; color: #1E293B; margin: 32px 0 16px 0; padding-bottom: 8px; border-bottom: 2px solid #E2E8F0; }
    .insight-box { background: #EEF2FF; border-radius: 8px; padding: 16px; border-left: 4px solid #4F46E5; margin: 12px 0; font-size: 14px; color: #3730A3; }
    div[data-testid="stSidebar"] { background: #1E293B; }
    div[data-testid="stSidebar"] .stMarkdown p, div[data-testid="stSidebar"] .stMarkdown label { color: #E2E8F0; }
    div[data-testid="stSidebar"] h1, div[data-testid="stSidebar"] h2, div[data-testid="stSidebar"] h3 { color: white; }
</style>
"""


def metric_card(label, value, delta=None, delta_positive=True, color="#4F46E5"):
    """Render a styled metric card."""
    from html import escape
    label = escape(str(label))
    value = escape(str(value))
    delta_html = ""
    if delta is not None:
        cls = "delta-positive" if delta_positive else "delta-negative"
        arrow = "&#9650;" if delta_positive else "&#9660;"
        delta_html = f'<div class="delta {cls}">{arrow} {escape(str(delta))}</div>'
    return f"""
    <div class="metric-card" style="border-left-color: {color};">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        {delta_html}
    </div>
    """
