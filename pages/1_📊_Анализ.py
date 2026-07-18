import streamlit as st

from core.data import (load_ticker, fmt_large, fmt_pct, fmt_mult, load_risk_free)
from core.dcf import run_dcf
from core.dcf_analysis import implied_growth, implied_return, sensitivity_grid
from core.favorites import add_favorite
from core.wacc import estimate_wacc, ERP
from ui.theme import inject_theme
from ui.sidebar import render_sidebar
from ui import components as C

st.set_page_config(page_title="Анализ · Stock Analysator", page_icon="📊", layout="wide")
inject_theme()
params = render_sidebar()

ticker = st.text_input("Тикер", value="AAPL",
                       placeholder="AAPL, MSFT, NVDA...").upper().strip()
if not ticker:
    st.info("Введи тикер выше")
    st.stop()

with st.spinner(f"Загружаю данные по {ticker}..."):
    td = load_ticker(ticker)

if td is None:
    st.error(f"Тикер «{ticker}» не найден или данных нет.")
    st.stop()

# ─── Хедер + кнопка в избранное ─────────────────────────────────────────────
head, fav = st.columns([6, 1])
with head:
    st.markdown(f"# {td.name} &nbsp; `{td.symbol}`")
    site = f" · [{td.website}]({td.website})" if td.website else ""
    st.markdown(f"**{td.sector}** · {td.industry} · {td.country}{site}")
with fav:
    if st.button("⭐ В избранное", use_container_width=True):
        add_favorite(td.symbol)
        st.toast(f"{td.symbol} добавлен в избранное")

st.markdown("---")

# ─── Цена + быстрые метрики ─────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
arrow = "▲" if td.day_change_pct >= 0 else "▼"
c1.metric("Цена", f"{td.price:.2f} {td.currency}", f"{arrow} {abs(td.day_change_pct):.2f}%")
c2.metric("Рын. капитализация", fmt_large(td.market_cap))
c3.metric("EV", fmt_large(td.enterprise_value))
c4.metric("52w High", f"{td.week52_high:.2f}" if td.week52_high else "N/A")
c5.metric("52w Low", f"{td.week52_low:.2f}" if td.week52_low else "N/A")

C.price_chart(td.history)

# ─── Мультипликаторы ────────────────────────────────────────────────────────
C.section_header("📊 Мультипликаторы")
m = st.columns(8)
m[0].metric("P/E", fmt_mult(td.trailing_pe))
m[1].metric("Forward P/E", fmt_mult(td.forward_pe))
m[2].metric("P/S", fmt_mult(td.price_to_sales))
m[3].metric("P/B", fmt_mult(td.price_to_book))
m[4].metric("EV/EBITDA", fmt_mult(td.ev_to_ebitda))
m[5].metric("EV/Revenue", fmt_mult(td.ev_to_revenue))
m[6].metric("PEG", fmt_mult(td.peg))
m[7].metric("Div. Yield", fmt_pct(td.dividend_yield))

# ─── Финансы TTM ────────────────────────────────────────────────────────────
C.section_header("💰 Финансовые показатели (TTM)")
f = st.columns(6)
f[0].metric("Выручка", fmt_large(td.total_revenue))
f[1].metric("Валовая прибыль", fmt_large(td.gross_profits))
f[2].metric("EBITDA", fmt_large(td.ebitda))
f[3].metric("Чистая прибыль", fmt_large(td.net_income))
f[4].metric("FCF", fmt_large(td.free_cashflow))
f[5].metric("Долг", fmt_large(td.total_debt))
f2 = st.columns(6)
f2[0].metric("Gross Margin", fmt_pct(td.gross_margins))
f2[1].metric("EBITDA Margin", fmt_pct(td.ebitda_margins))
f2[2].metric("Net Margin", fmt_pct(td.profit_margins))
f2[3].metric("ROE", fmt_pct(td.roe))
f2[4].metric("ROA", fmt_pct(td.roa))
f2[5].metric("Рост выручки", fmt_pct(td.revenue_growth))

with st.expander("ℹ️ О компании"):
    st.write(td.description)
    d = st.columns(4)
    d[0].metric("Сотрудников", f"{td.employees:,}" if td.employees else "N/A")
    d[1].metric("Акций в обращ.", fmt_large(td.shares_outstanding))
    d[2].metric("Beta", fmt_mult(td.beta, ""))
    d[3].metric("Short Float %", fmt_pct(td.short_percent_float))

# ─── DCF ────────────────────────────────────────────────────────────────────
C.section_header("🔮 DCF — три сценария")
# База FCF: с поправкой на SBC (если галочка и данные есть) или без неё
use_sbc = params.subtract_sbc and td.fcf_normalized_ex_sbc is not None
fcf_base = td.fcf_normalized_ex_sbc if use_sbc else td.fcf_normalized

# ─── Действующий WACC: CAPM по бете (auto) или ползунок ─────────────────────
rf, rf_live = load_risk_free()
wacc_est = (estimate_wacc(td.beta, rf, td.market_cap, td.total_debt)
            if params.wacc_auto else None)
eff_wacc = wacc_est.wacc if wacc_est is not None else params.wacc

if not td.shares_outstanding:
    st.warning("Недостаточно данных для DCF (нет количества акций).")
elif not fcf_base or fcf_base <= 0:
    st.info((
        f"**DCF по свободному денежному потоку неприменим.** У «{td.symbol}» "
        f"нормализованный FCF отрицательный или отсутствует "
        f"(норм. FCF: {fmt_large(fcf_base)}, TTM: {fmt_large(td.free_cashflow)}). "
        "Компанию, сжигающую кэш, нельзя оценить простой FCF-моделью — "
        "справедливая цена не рассчитывается."
    ).replace("$", "\\$"))
else:
    dcf = run_dcf(
        fcf_base=fcf_base, growth_rates=params.growth_rates,
        wacc=eff_wacc, terminal_growth=params.terminal_growth,
        years=params.years, shares=td.shares_outstanding, net_debt=td.net_debt,
    )
    cols = st.columns(3)
    for col, name in zip(cols, ["bear", "base", "bull"]):
        C.scenario_card(col, name, dcf[name], td.price)

    # Показываем, какая база FCF использована (медиана лет vs единичный TTM).
    base_note = f"База FCF: {fmt_large(fcf_base)}"
    if use_sbc:
        base_note += f" (за вычетом SBC {fmt_large(td.sbc_normalized)})"
    elif params.subtract_sbc:
        base_note += " (данных по SBC нет)"
    if td.free_cashflow and abs(fcf_base - td.free_cashflow) > 0.05 * abs(td.free_cashflow):
        base_note += f" · TTM был {fmt_large(td.free_cashflow)}"
    st.caption((f"{base_note} · WACC: {eff_wacc*100:.1f}% · Терм. рост: "
                f"{params.terminal_growth*100:.1f}% · Горизонт: {params.years} лет · "
                f"Чистый долг: {fmt_large(td.net_debt)}").replace("$", "\\$"))
    if wacc_est is not None:
        wacc_note = (f"WACC {eff_wacc*100:.1f}% = CAPM: rf {wacc_est.risk_free*100:.1f}%"
                     f" + β {wacc_est.beta_used:.2f} × ERP {ERP*100:.0f}%")
        if wacc_est.beta_used != wacc_est.beta_raw:
            wacc_note += f" (бета {wacc_est.beta_raw:.2f} ограничена)"
        if wacc_est.debt_weight > 0.01:
            wacc_note += " · долг учтён"
        if not rf_live:
            wacc_note += " · rf по умолчанию (нет ^TNX)"
        st.caption(wacc_note)
    elif params.wacc_auto:
        st.caption(f"WACC {eff_wacc*100:.1f}% — ползунок (нет беты для CAPM).")
    st.caption("⚠️ Оценка по текущему FCF: быстрорастущие компании (AMZN, NVDA) "
               "обычно выглядят «дорогими» — модель не закладывает будущий рост "
               "маржи. Чистый долг из Yahoo включает лизинг, что занижает оценку.")

    # ─── Реверс-DCF: что заложено в цену ────────────────────────────────────
    C.section_header("🔍 Что заложено в цену")
    ig = implied_growth(
        price=td.price, fcf_base=fcf_base, shares=td.shares_outstanding,
        net_debt=td.net_debt, wacc=eff_wacc,
        terminal_growth=params.terminal_growth, years=params.years,
    )
    ir = implied_return(
        price=td.price, fcf_base=fcf_base, shares=td.shares_outstanding,
        net_debt=td.net_debt, growth_start=params.growth_rates["base"],
        terminal_growth=params.terminal_growth, years=params.years,
    )
    C.reverse_dcf_cards(ig, ir, params.terminal_growth, td.revenue_growth)
    st.caption("Обратная задача: какой рост и какая доходность должны быть, "
               "чтобы справедливая цена совпала с рыночной. Двигай ползунки — "
               "цифры пересчитываются.")

    max_tv = max(r.tv_share for r in dcf.values())
    if max_tv > 0.75:
        st.warning(f"⚠️ Терминальная стоимость даёт до {max_tv*100:.0f}% оценки — "
                   "результат сильно зависит от WACC и терминального роста. "
                   "Увеличь горизонт или снизь стартовый рост.")

    st.markdown("##### Структура стоимости (Base сценарий)")
    C.dcf_waterfall(dcf["base"], params.years)
    st.markdown("##### Справедливая цена vs текущая")
    C.dcf_fair_value(dcf, td.price)

    with st.expander("📐 Таблица чувствительности (WACC × терминальный рост)"):
        mode_label = st.radio("Показывать", ["Апсайд %", "Справедливая цена $"],
                              horizontal=True, key="sens_mode")
        grid = sensitivity_grid(
            fcf_base=fcf_base, price=td.price, shares=td.shares_outstanding,
            net_debt=td.net_debt, growth_start=params.growth_rates["base"],
            wacc=eff_wacc, terminal_growth=params.terminal_growth,
            years=params.years,
        )
        if grid is None:
            st.caption("Недостаточно данных для расчёта.")
        else:
            C.sensitivity_table(grid, "price" if mode_label.startswith("Справ") else "upside")
            st.caption("Жёлтой рамкой отмечены твои текущие настройки. "
                       "«—» — там терминальный рост ≥ WACC, модель Гордона неприменима.")

C.section_header("📅 История финансов")
C.financials_history(td.financials)

st.markdown("---")
if td.history is not None and not td.history.empty:
    _ts = td.history.index[-1]
    st.caption(f"Данные: Yahoo Finance · цена на {_ts.strftime('%d.%m.%Y %H:%M')}")
st.caption("⚠️ Только для образовательных целей. Не является инвестиционной рекомендацией.")
