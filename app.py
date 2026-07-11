import streamlit as st
from ui.theme import inject_theme
from ui.sidebar import render_sidebar

st.set_page_config(page_title="Stock Analysator", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")
inject_theme()
render_sidebar()  # слайдеры видны на всех страницах; параметры читаются на страницах

st.markdown("# 📈 Stock Analysator")
st.markdown("""
Анализ акций US-рынка: метрики, мультипликаторы, финансы и **DCF-оценка по трём
сценариям** (Bear / Base / Bull).

**Слева в меню:**
- 📊 **Анализ** — ввести тикер, получить метрики, график и DCF.
- ⚖️ **Сравнение** — сравнить несколько тикеров в таблице.
- ⭐ **Избранное** — сохранённые тикеры (хранятся в твоём браузере).
""")
st.caption("⚠️ Только для образовательных целей. Не является инвестиционной рекомендацией.")
