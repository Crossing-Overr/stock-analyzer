import streamlit as st

_CSS = """
<style>
    .metric-card { background:#1e1e2e; border:1px solid #313244; border-radius:12px; padding:16px 20px; margin:4px 0; }
    .metric-label { color:#a6adc8; font-size:12px; text-transform:uppercase; letter-spacing:0.05em; }
    .metric-value { color:#cdd6f4; font-size:22px; font-weight:700; margin-top:4px; }
    .metric-sub { color:#6c7086; font-size:12px; margin-top:2px; }
    .scenario-bull { border-left:4px solid #a6e3a1; }
    .scenario-base { border-left:4px solid #89b4fa; }
    .scenario-bear { border-left:4px solid #f38ba8; }
    .upside-pos { color:#a6e3a1; font-weight:700; }
    .upside-neg { color:#f38ba8; font-weight:700; }
    .section-header { color:#cdd6f4; font-size:18px; font-weight:600; margin:24px 0 12px 0; padding-bottom:8px; border-bottom:1px solid #313244; }
    div[data-testid="stMetric"] { background:#1e1e2e; border:1px solid #313244; border-radius:12px; padding:12px 16px; }
    .cmp-best { color:#a6e3a1; font-weight:700; }
    .cmp-worst { color:#f38ba8; }
</style>
"""


def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
