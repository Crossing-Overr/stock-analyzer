from dataclasses import dataclass
import streamlit as st


@dataclass
class DcfParams:
    years: int
    wacc: float
    terminal_growth: float
    growth_rates: dict   # {"bear":..,"base":..,"bull":..}


def render_sidebar() -> DcfParams:
    with st.sidebar:
        st.markdown("## 📈 Stock Analysator")
        st.markdown("---")
        st.markdown("### ⚙️ DCF параметры")
        years = st.slider("Горизонт прогноза (лет)", 3, 10, 5)
        wacc = st.slider("WACC (%)", 5.0, 20.0, 10.0, 0.5) / 100
        terminal_growth = st.slider("Терминальный рост (%)", 1.0, 5.0, 2.5, 0.25) / 100

        st.markdown("#### Стартовый рост FCF (%/год)")
        st.caption("Рост в 1-й год. Дальше линейно затухает к терминальному.")
        bull_g = st.slider("🐂 Bull", 5, 40, 15) / 100
        base_g = st.slider("📊 Base", 0, 30, 8) / 100
        bear_g = st.slider("🐻 Bear", -10, 15, 2) / 100

        st.markdown("---")
        st.caption("Данные: Yahoo Finance (yfinance)")

    return DcfParams(
        years=years, wacc=wacc, terminal_growth=terminal_growth,
        growth_rates={"bear": bear_g, "base": base_g, "bull": bull_g},
    )
