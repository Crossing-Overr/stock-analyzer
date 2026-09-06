import streamlit as st

from core.data import (load_ticker, fmt_large, fmt_pct, fmt_mult, load_risk_free)
from core.dcf import run_dcf
from core.dcf_analysis import implied_growth, implied_return, sensitivity_grid
from core.favorites import add_favorite
from core.wacc import estimate_wacc_for, ERP
from ui.theme import inject_theme
from ui.sidebar import render_sidebar
from ui import components as C

st.set_page_config(page_title="Анализ · Stock Analysator", page_icon="📊", layout="wide")
inject_theme()
params = render_sidebar()

_prefill = st.session_state.pop("ticker_prefill", "AAPL")
ticker = st.text_input("Тикер", value=_prefill,
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
    C.ticker_header(td)
with fav:
    if st.button("⭐ В избранное", use_container_width=True):
        add_favorite(td.symbol)
        st.toast(f"{td.symbol} добавлен в избранное")

# База FCF: с поправкой на SBC (если галочка и данные есть) или без неё
use_sbc = params.subtract_sbc and td.fcf_normalized_ex_sbc is not None
fcf_base = td.fcf_normalized_ex_sbc if use_sbc else td.fcf_normalized

# ─── Действующий WACC: CAPM по бете (auto) или ползунок ─────────────────────
rf, rf_live = load_risk_free()
wacc_est = estimate_wacc_for(td, rf) if params.wacc_auto else None
eff_wacc = wacc_est.wacc if wacc_est is not None else params.wacc

if not td.shares_outstanding:
    st.warning("Недостаточно данных для DCF (нет количества акций).")
    dcf = None
elif not fcf_base or fcf_base <= 0:
    st.info((
        f"**DCF по свободному денежному потоку неприменим.** У «{td.symbol}» "
        f"нормализованный FCF отрицательный или отсутствует "
        f"(норм. FCF: {fmt_large(fcf_base)}, TTM: {fmt_large(td.free_cashflow)}). "
        "Компанию, сжигающую кэш, нельзя оценить простой FCF-моделью — "
        "справедливая цена не рассчитывается."
    ).replace("$", "\\$"))
    dcf = None
else:
    dcf = run_dcf(
        fcf_base=fcf_base, growth_rates=params.growth_rates,
        wacc=eff_wacc, terminal_growth=params.terminal_growth,
        years=params.years, shares=td.shares_outstanding, net_debt=td.net_debt,
        terminal_multiple=params.terminal_multiple,
    )
    C.verdict_card(dcf, td.price, eff_wacc)

    ig = implied_growth(
        price=td.price, fcf_base=fcf_base, shares=td.shares_outstanding,
        net_debt=td.net_debt, wacc=eff_wacc,
        terminal_growth=params.terminal_growth, years=params.years,
        terminal_multiple=params.terminal_multiple,
    )
    ir = implied_return(
        price=td.price, fcf_base=fcf_base, shares=td.shares_outstanding,
        net_debt=td.net_debt, growth_start=params.growth_rates["base"],
        terminal_growth=params.terminal_growth, years=params.years,
        terminal_multiple=params.terminal_multiple,
    )
    C.reverse_dcf_cards(ig, ir, params.terminal_growth, td.revenue_growth, rf)

    base_note = f"База FCF: {fmt_large(fcf_base)}"
    if use_sbc:
        base_note += f" (за вычетом SBC {fmt_large(td.sbc_normalized)})"
    elif params.subtract_sbc:
        base_note += " (данных по SBC нет)"
    wacc_note = ""
    if wacc_est is not None:
        wacc_note = (f" · WACC {eff_wacc*100:.1f}% = rf {wacc_est.risk_free*100:.1f}%"
                     f" + β {wacc_est.beta_used:.2f} × ERP {ERP*100:.0f}%")
    # Эквивалент Гордона в мультипликаторах: (1+g)/(WACC−g). Сильно зависит от WACC
    # (у защитных имён с низкой бетой он куда выше), поэтому показываем для сравнения.
    _g = min(params.terminal_growth, eff_wacc - 1e-3)
    gordon_x = (1 + _g) / (eff_wacc - _g)
    term_note = (f"терминал {params.terminal_multiple:.0f}x FCF "
                 f"(Гордон здесь дал бы {gordon_x:.1f}x)"
                 if params.terminal_multiple
                 else f"терм. рост {params.terminal_growth*100:.1f}% (это {gordon_x:.1f}x FCF)")
    st.caption((f"{base_note}{wacc_note} · горизонт {params.years} лет · "
                f"{term_note}").replace("$", "\\$"))
    st.caption("⚠️ Оценка по текущему FCF: быстрорастущие компании обычно выглядят "
               "«дорогими» — модель не закладывает будущий рост маржи. Чистый долг "
               "из Yahoo включает лизинг, что занижает оценку.")

C.price_chart(td.history)

C.section_header("Ключевые метрики")
C.metric_rows([
    ("P/E · Forward P/E", f"{fmt_mult(td.trailing_pe)} · {fmt_mult(td.forward_pe)}"),
    ("EV/EBITDA", fmt_mult(td.ev_to_ebitda)),
    ("Чистая маржа", fmt_pct(td.profit_margins)),
    ("ROE", fmt_pct(td.roe)),
    ("Рост выручки", fmt_pct(td.revenue_growth)),
    ("Капитализация", fmt_large(td.market_cap)),
])

with st.expander("📊 Все мультипликаторы"):
    m = st.columns(4)
    m[0].metric("P/E", fmt_mult(td.trailing_pe))
    m[1].metric("Forward P/E", fmt_mult(td.forward_pe))
    m[2].metric("P/S", fmt_mult(td.price_to_sales))
    m[3].metric("P/B", fmt_mult(td.price_to_book))
    m2 = st.columns(4)
    m2[0].metric("EV/EBITDA", fmt_mult(td.ev_to_ebitda))
    m2[1].metric("EV/Revenue", fmt_mult(td.ev_to_revenue))
    m2[2].metric("PEG", fmt_mult(td.peg))
    m2[3].metric("Div. Yield", fmt_pct(td.dividend_yield))
    d = st.columns(4)
    d[0].metric("52w High", f"{td.week52_high:.2f}" if td.week52_high else "N/A")
    d[1].metric("52w Low", f"{td.week52_low:.2f}" if td.week52_low else "N/A")
    d[2].metric("EV", fmt_large(td.enterprise_value))
    d[3].metric("Beta", fmt_mult(td.beta, ""))

with st.expander("💰 Финансы (TTM)"):
    f = st.columns(4)
    f[0].metric("Выручка", fmt_large(td.total_revenue))
    f[1].metric("Валовая прибыль", fmt_large(td.gross_profits))
    f[2].metric("EBITDA", fmt_large(td.ebitda))
    f[3].metric("Чистая прибыль", fmt_large(td.net_income))
    f2 = st.columns(4)
    f2[0].metric("FCF", fmt_large(td.free_cashflow))
    f2[1].metric("Долг", fmt_large(td.total_debt))
    f2[2].metric("Gross Margin", fmt_pct(td.gross_margins))
    f2[3].metric("ROA", fmt_pct(td.roa))

with st.expander("ℹ️ О компании"):
    st.write(td.description)
    d2 = st.columns(3)
    d2[0].metric("Сотрудников", f"{td.employees:,}" if td.employees else "N/A")
    d2[1].metric("Акций в обращ.", fmt_large(td.shares_outstanding))
    d2[2].metric("Short Float %", fmt_pct(td.short_percent_float))

if dcf is not None:
    with st.expander("🔮 Детали DCF — сценарии, структура, чувствительность"):
        cols = st.columns(3)
        for col, name in zip(cols, ["bear", "base", "bull"]):
            C.scenario_card(col, name, dcf[name], td.price)

        max_tv = max(r.tv_share for r in dcf.values())
        if max_tv > 0.75:
            st.warning(f"⚠️ Терминальная стоимость даёт до {max_tv*100:.0f}% оценки — "
                       "результат сильно зависит от WACC и терминального роста.")

        st.markdown("##### Структура стоимости (Base)")
        C.dcf_waterfall(dcf["base"], params.years)
        st.markdown("##### Справедливая цена vs текущая")
        C.dcf_fair_value(dcf, td.price)

        _axis = "мультипликатор" if params.terminal_multiple else "терминальный рост"
        st.markdown(f"##### Чувствительность (WACC × {_axis})")
        mode_label = st.radio("Показывать", ["Апсайд %", "Справедливая цена $"],
                              horizontal=True, key="sens_mode")
        grid = sensitivity_grid(
            fcf_base=fcf_base, price=td.price, shares=td.shares_outstanding,
            net_debt=td.net_debt, growth_start=params.growth_rates["base"],
            wacc=eff_wacc, terminal_growth=params.terminal_growth,
            years=params.years, terminal_multiple=params.terminal_multiple,
        )
        if grid is None:
            st.caption("Недостаточно данных для расчёта.")
        else:
            C.sensitivity_table(grid, "price" if mode_label.startswith("Справ") else "upside")
            st.caption("Жёлтой рамкой отмечены текущие настройки. «—» — терминальный "
                       "рост ≥ WACC, модель Гордона неприменима.")

with st.expander("📅 История финансов"):
    C.financials_history(td.financials)

st.markdown("---")
if td.history is not None and not td.history.empty:
    _ts = td.history.index[-1]
    st.caption(f"Данные: Yahoo Finance · цена на {_ts.strftime('%d.%m.%Y %H:%M')}")
st.caption("⚠️ Только для образовательных целей. Не является инвестиционной рекомендацией.")
