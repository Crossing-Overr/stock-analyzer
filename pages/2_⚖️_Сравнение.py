import streamlit as st

from core.data import load_ticker, load_risk_free
from core.compare import build_comparison_table
from core.dcf_analysis import ticker_base_upside
from core.favorites import get_favorites
from ui.theme import inject_theme, COLORS
from ui.sidebar import render_sidebar

st.set_page_config(page_title="Сравнение · Stock Analysator", page_icon="⚖️", layout="wide")
inject_theme()
params = render_sidebar()

st.markdown("# ⚖️ Сравнение тикеров")

default = ", ".join(get_favorites()) or "AAPL, MSFT, NVDA"
raw = st.text_input("Тикеры через запятую", value=default,
                    placeholder="AAPL, MSFT, NVDA")
symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]

if not symbols:
    st.info("Введи хотя бы один тикер")
    st.stop()

with st.spinner("Загружаю данные..."):
    tickers = []
    missing = []
    for sym in symbols:
        td = load_ticker(sym)
        if td is not None:
            tickers.append(td)
        else:
            missing.append(sym)

if missing:
    st.warning("Не найдены: " + ", ".join(missing))
if not tickers:
    st.stop()

# апсайд Base-сценария: SBC-консистентная база + per-ticker CAPM-WACC
rf, _rf_live = load_risk_free()
base_upsides = {td.symbol: ticker_base_upside(td, params, rf) for td in tickers}

table = build_comparison_table(tickers, base_upsides)

# ─── Рендер HTML-таблицы с подсветкой best/worst ────────────────────────────
header = "".join(f"<th style='padding:8px 14px;text-align:right'>{c}</th>" for c in table.columns)
rows_html = ""
for row in table.rows:
    cells = ""
    for i, disp in enumerate(row.display_values):
        cls = ""
        if i == row.best_index:
            cls = "cmp-best"
        elif i == row.worst_index:
            cls = "cmp-worst"
        cells += f"<td class='{cls}' style='padding:8px 14px;text-align:right'>{disp}</td>"
    rows_html += (f"<tr><td style='padding:8px 14px;color:{COLORS['text_dim']}'>{row.label}</td>{cells}</tr>")

st.markdown(f"""
<table style='width:100%;border-collapse:collapse;background:{COLORS['surface']};
border:1px solid {COLORS['border']};border-radius:12px'>
<thead><tr><th style='padding:8px 14px;text-align:left'>Метрика</th>{header}</tr></thead>
<tbody>{rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

wacc_txt = "CAPM по бете каждого тикера" if params.wacc_auto else f"{params.wacc*100:.1f}%"
st.caption(f"Апсайд считается по Base-сценарию DCF при текущих слайдерах "
           f"(WACC: {wacc_txt}, горизонт {params.years} лет). "
           "Зелёным — лучшее в строке, красным — худшее.")
st.markdown("---")
st.caption("⚠️ Только для образовательных целей. Не является инвестиционной рекомендацией.")
