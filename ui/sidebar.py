from dataclasses import dataclass
from typing import Optional
import streamlit as st


@dataclass
class DcfParams:
    years: int
    wacc: float          # значение ползунка — используется в ручном режиме
    wacc_auto: bool      # True → страницы считают WACC по CAPM (бета тикера)
    terminal_growth: float
    terminal_multiple: Optional[float]   # None → терминал по Гордону
    growth_rates: dict   # {"bear":..,"base":..,"bull":..}
    subtract_sbc: bool


def render_sidebar() -> DcfParams:
    with st.sidebar:
        st.markdown("## 📈 Stock Analysator")
        st.markdown("---")
        st.markdown("### ⚙️ DCF параметры")
        # key= обязателен: иначе значения сбрасываются при смене вкладки
        years = st.slider("Горизонт прогноза (лет)", 3, 15, 10, key="dcf_years")

        wacc_auto = st.checkbox(
            "WACC автоматически (CAPM)", value=True, key="dcf_wacc_auto",
            help="Ставка из беты тикера: rf(10-летки) + β × 5%, с учётом долга. "
                 "У каждой компании — своя. Сними галочку, чтобы задать вручную.",
        )
        if wacc_auto:
            st.caption("WACC считается по бете тикера — см. подпись под DCF.")
            wacc = st.session_state.get("dcf_wacc", 10.0) / 100
        else:
            wacc = st.slider("WACC (%)", 5.0, 20.0, 10.0, 0.5, key="dcf_wacc") / 100

        term_mode = st.radio(
            "Терминальная стоимость", ["Рост (Гордон)", "Мультипликатор"],
            key="dcf_term_mode",
            help="Гордон: вечная рента при заданном росте. Мультипликатор (подход "
                 "Карлина): «во сколько FCF оценят компанию в конце горизонта» — "
                 "нынешний Гордон при WACC 10% эквивалентен всего ≈13.5x.",
        )
        terminal_growth = st.slider("Терминальный рост (%)", 1.0, 5.0, 2.5, 0.25,
                                    key="dcf_tg") / 100
        if term_mode == "Мультипликатор":
            terminal_multiple = float(st.slider(
                "Мультипликатор к FCF последнего года", 5, 40, 15, 1, key="dcf_mult"))
            st.caption("Терминальный рост в этом режиме не влияет на терминал, "
                       "но задаёт, к чему затухает рост FCF.")
        else:
            terminal_multiple = None

        st.markdown("#### Стартовый рост FCF (%/год)")
        st.caption("Рост в 1-й год. Дальше линейно затухает к терминальному.")
        bull_g = st.slider("🐂 Bull", 5, 40, 15, key="dcf_bull") / 100
        base_g = st.slider("📊 Base", 0, 30, 8, key="dcf_base") / 100
        bear_g = st.slider("🐻 Bear", -10, 15, 2, key="dcf_bear") / 100

        st.markdown("---")
        subtract_sbc = st.checkbox(
            "Вычитать SBC из FCF", value=True, key="dcf_sbc",
            help="Компенсация акциями — реальные расходы: она размывает твою долю. "
                 "Yahoo её из FCF не вычитает, поэтому оценка получается завышенной.",
        )

        st.markdown("---")
        st.caption("Данные: Yahoo Finance (yfinance)")

    return DcfParams(
        years=years, wacc=wacc, wacc_auto=wacc_auto,
        terminal_growth=terminal_growth, terminal_multiple=terminal_multiple,
        growth_rates={"bear": bear_g, "base": base_g, "bull": bull_g},
        subtract_sbc=subtract_sbc,
    )
