import streamlit as st

_CSS = """
<style>
    .metric-card { background:#1e1e2e; border:1px solid #45475a; border-radius:12px; padding:16px 20px; margin:4px 0; }
    .metric-label { color:#bac2de; font-size:12px; text-transform:uppercase; letter-spacing:0.05em; }
    .metric-value { color:#f5f5fa; font-size:22px; font-weight:700; margin-top:4px; overflow-wrap:anywhere; }
    .metric-sub { color:#a6adc8; font-size:12px; margin-top:2px; line-height:1.5; }
    .scenario-bull { border-left:4px solid #a6e3a1; }
    .scenario-base { border-left:4px solid #89b4fa; }
    .scenario-bear { border-left:4px solid #f38ba8; }
    .upside-pos { color:#a6e3a1; font-weight:700; }
    .upside-neg { color:#f38ba8; font-weight:700; }
    .section-header { color:#f5f5fa; font-size:18px; font-weight:600; margin:24px 0 12px 0; padding-bottom:8px; border-bottom:1px solid #45475a; }

    /* st.metric: тёмная карточка + гарантированный контраст текста */
    div[data-testid="stMetric"] { background:#1e1e2e; border:1px solid #45475a; border-radius:12px; padding:12px 16px; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color:#f5f5fa; font-size:1.5rem; line-height:1.2;
        overflow-wrap:anywhere; white-space:normal;
    }
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] { color:#bac2de; overflow-wrap:anywhere; }
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] p { font-size:0.8rem; }

    .cmp-best { color:#a6e3a1; font-weight:700; }
    .cmp-worst { color:#f38ba8; font-weight:600; }
</style>
"""


def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
