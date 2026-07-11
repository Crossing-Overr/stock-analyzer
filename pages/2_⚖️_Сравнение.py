import streamlit as st

from core.data import load_ticker
from core.dcf import run_dcf
from core.compare import build_comparison_table
from core.favorites import get_favorites
from ui.theme import inject_theme
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

# апсайд Base-сценария для каждого
base_upsides = {}
for td in tickers:
    if td.free_cashflow and td.shares_outstanding and td.price:
        dcf = run_dcf(fcf_base=td.free_cashflow, growth_rates=params.growth_rates,
                      wacc=params.wacc, terminal_growth=params.terminal_growth,
                      years=params.years, shares=td.shares_outstanding, net_debt=td.net_debt)
        iv = dcf["base"].intrinsic
        base_upsides[td.symbol] = (iv - td.price) / td.price * 100 if iv > 0 else None
    else:
        base_upsides[td.symbol] = None

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
    rows_html += (f"<tr><td style='padding:8px 14px;color:#a6adc8'>{row.label}</td>{cells}</tr>")

st.markdown(f"""
<table style='width:100%;border-collapse:collapse;background:#1e1e2e;
border:1px solid #313244;border-radius:12px'>
<thead><tr><th style='padding:8px 14px;text-align:left'>Метрика</th>{header}</tr></thead>
<tbody>{rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

st.caption(f"Апсайд считается по Base-сценарию DCF при текущих слайдерах "
           f"(WACC {params.wacc*100:.1f}%, горизонт {params.years} лет). "
           "Зелёным — лучшее в строке, красным — худшее.")
st.markdown("---")
st.caption("⚠️ Только для образовательных целей. Не является инвестиционной рекомендацией.")
