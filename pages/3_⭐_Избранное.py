import streamlit as st

from core.data import load_ticker, fmt_large
from core.dcf import dcf_upside_base
from core.favorites import get_favorites, add_favorite, remove_favorite
from ui.theme import inject_theme
from ui.sidebar import render_sidebar

st.set_page_config(page_title="Избранное · Stock Analysator", page_icon="⭐", layout="wide")
inject_theme()
params = render_sidebar()

st.markdown("# ⭐ Избранное")
st.caption("Избранное хранится на время сессии (пока открыта вкладка). "
           "Постоянное хранение в браузере — следующий шаг.")

# добавление вручную
add_col, _ = st.columns([2, 4])
with add_col:
    new_sym = st.text_input("Добавить тикер", placeholder="TSLA").upper().strip()
    if st.button("➕ Добавить") and new_sym:
        add_favorite(new_sym)
        st.rerun()

favorites = get_favorites()
if not favorites:
    st.info("Пока пусто. Добавь тикер выше или кнопкой «⭐ В избранное» на вкладке Анализ.")
    st.stop()

for sym in favorites:
    td = load_ticker(sym)
    c_name, c_price, c_chg, c_up, c_del = st.columns([3, 2, 2, 2, 1])
    if td is None:
        c_name.markdown(f"**{sym}** — данные недоступны")
    else:
        arrow = "▲" if td.day_change_pct >= 0 else "▼"
        c_name.markdown(f"**{sym}** · {td.name}")
        c_price.metric("Цена", f"{td.price:.2f}")
        c_chg.metric("Δ день", f"{arrow} {abs(td.day_change_pct):.2f}%")
        up = dcf_upside_base(
            td.fcf_normalized, td.price, td.shares_outstanding, td.net_debt,
            params.growth_rates, params.wacc, params.terminal_growth, params.years,
        )
        c_up.metric("Апсайд Base", f"{up:+.1f}%" if up is not None else "N/A")
    if c_del.button("🗑", key=f"del_{sym}"):
        remove_favorite(sym)
        st.rerun()

st.markdown("---")
st.caption("⚠️ Только для образовательных целей. Не является инвестиционной рекомендацией.")
