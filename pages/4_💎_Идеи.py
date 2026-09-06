import os
import streamlit as st

from core.data import fmt_large, load_prices
from core.screener import screen, load_snapshot, PRESETS, ScreenFilters
from ui.theme import inject_theme

st.set_page_config(page_title="Идеи · Stock Analysator", page_icon="💎", layout="wide")
inject_theme()

SNAPSHOT = os.path.join(os.path.dirname(__file__), "..", "data", "sp500_snapshot.json")

st.markdown("# 💎 Идеи — куда присмотреться")

if not os.path.exists(SNAPSHOT):
    st.warning("Снимок ещё не построен. Запусти `python3 scripts/build_snapshot.py` "
               "и обнови страницу.")
    st.stop()

snap = load_snapshot(SNAPSHOT)

# ─── Пресеты ─────────────────────────────────────────────────────────────────
if "preset" not in st.session_state:
    st.session_state.preset = "undervalued"

cols = st.columns(len(PRESETS))
for col, (pid, preset) in zip(cols, PRESETS.items()):
    kind = "primary" if st.session_state.preset == pid else "secondary"
    if col.button(preset.label, key=f"preset_{pid}", type=kind, use_container_width=True):
        st.session_state.preset = pid
        st.rerun()

active = PRESETS[st.session_state.preset]
st.caption(active.describe)

# ─── Тонкая настройка ────────────────────────────────────────────────────────
with st.expander("⚙️ Тонкая настройка фильтров"):
    f1, f2, f3 = st.columns(3)
    min_up = f1.slider("Мин. апсайд Base (%)", -50, 100, -20, 5, key="idea_min_up")
    max_pe = f2.slider("Макс. P/E", 5, 80, 60, 1, key="idea_max_pe")
    min_rg = f3.slider("Мин. рост выручки (%)", -30, 40, -30, 5, key="idea_min_rg")
    cap_lo, cap_hi = st.slider("Капитализация ($ млрд)", 0, 5000, (0, 5000), 10,
                               key="idea_cap")
    st.caption("Капитализация: в S&P 500 все компании крупные — этим ползунком можно, "
               "например, исключить триллионников и смотреть на имена поменьше. "
               "Только положительный FCF — всегда включено.")

filters = ScreenFilters(
    min_upside=float(min_up), max_pe=float(max_pe), min_revenue_growth=min_rg / 100,
    min_market_cap=cap_lo * 1e9 if cap_lo > 0 else None,
    max_market_cap=cap_hi * 1e9 if cap_hi < 5000 else None,
)
res = screen(snap, st.session_state.preset, filters, limit=20)

# ─── Вариант B: живые цены у показанных карточек ────────────────────────────
# Справедливая цена (из снимка) не зависит от текущей цены, поэтому апсайд
# показанных карточек пересчитываем на живую цену без повторного DCF. Порядок —
# из снимка (шорт-лист), обновляются только цифры на экране.
live = load_prices(tuple(r["symbol"] for r in res.rows))
for r in res.rows:
    lp = live.get(r["symbol"])
    up = r.get("upside_base")
    if lp and up is not None and r.get("price"):
        fair = r["price"] * (1 + up / 100)
        r["price"] = lp
        r["upside_base"] = (fair - lp) / lp * 100

fresh = "· 🔄 цены обновлены сейчас" if live else ""
st.caption(f"Фундамент на {res.as_of} {fresh} · **{res.total_passed}** компаний прошло "
           f"фильтр · показаны топ-{len(res.rows)}")

if not res.rows:
    st.info("Ничего не найдено — ослабь фильтры или выбери другой пресет.")
    st.stop()

# ─── Карточки ────────────────────────────────────────────────────────────────
for r in res.rows:
    risk = r.get("badge") == "risk"
    border = "#3a2a45" if risk else "#313244"
    bg = "#171320" if risk else "#1e1e2e"
    up = r.get("upside_base")
    up_txt = f"{up:+.1f}%" if up is not None else "N/A"
    up_col = "#a6e3a1" if (up or 0) >= 0 else "#f38ba8"
    fair = r["price"] * (1 + up / 100) if (up is not None and r.get("price")) else None
    fair_txt = f"${fair:.2f}" if fair else "N/A"
    ig, rg = r.get("implied_growth"), r.get("revenue_growth")
    grow = (f"Заложен <b>{ig*100:.0f}%</b> · факт <b style='color:#a6e3a1'>{rg*100:.0f}%</b>"
            if (ig is not None and rg is not None) else "")
    badge = ("<span style='background:rgba(249,226,175,0.18);color:#f9e2af;font-size:10px;"
             "font-weight:700;padding:2px 7px;border-radius:6px;margin-left:7px'>⚠️ РИСК</span>"
             if risk else "")
    pe_txt = f"{r['pe']:.0f}" if r.get("pe") else "—"

    card, act = st.columns([9, 1])
    with card:
        st.markdown(f"""
        <div style="background:{bg};border:1px solid {border};border-radius:12px;
        padding:13px 16px;margin-bottom:4px;display:flex;align-items:center;gap:18px">
          <div style="min-width:150px">
            <div style="color:#cdd6f4;font-size:14px;font-weight:700">{r['symbol']}{badge}</div>
            <div style="color:#6c7086;font-size:11px">{(r.get('name') or '')[:26]}</div>
            <div style="color:#a6adc8;font-size:11px;margin-top:2px">${r['price']:.2f}</div>
          </div>
          <div style="flex:1">
            <div style="color:#6c7086;font-size:10px;text-transform:uppercase;letter-spacing:0.05em">Справедливая · Base</div>
            <div style="display:flex;align-items:baseline;gap:9px">
              <span style="color:#f5f5fa;font-size:20px;font-weight:700">{fair_txt}</span>
              <span style="color:{up_col};font-size:14px;font-weight:700">{up_txt}</span>
            </div>
          </div>
          <div style="text-align:right;min-width:180px">
            <div style="color:#a6adc8;font-size:11px">{grow}</div>
            <div style="color:#6c7086;font-size:11px;margin-top:2px">P/E {pe_txt} · кап. {fmt_large(r.get('market_cap'))}</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    if act.button("Анализ →", key=f"go_{r['symbol']}", use_container_width=True):
        st.session_state["ticker_prefill"] = r["symbol"]
        st.switch_page("pages/1_📊_Анализ.py")

st.markdown("---")
st.warning("⚠️ Это **не сигнал к покупке**, а список «куда посмотреть внимательнее». "
           "DCF-апсайд чувствителен к допущениям. Turnaround-идеи — максимальный риск: "
           "алгоритм видит «дёшево + фундамент», но не отличает временный спад от упадка. "
           "Кликни «Анализ →» для полного разбора с живыми данными.")
st.caption("Только для образовательных целей. Не является инвестиционной рекомендацией.")
