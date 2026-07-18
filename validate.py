#!/usr/bin/env python3
"""
Валидация цифр, логики модели, адекватности и актуальности.

Запуск:  python3 validate.py            # дефолтная корзина
         python3 validate.py AAPL KO    # свои тикеры

Каждая проверка печатает ✅/⚠️/❌ с цифрами. Выход с кодом 1, если есть ❌.
"""
import datetime
import sys
import warnings

warnings.filterwarnings("ignore")

import yfinance as yf  # noqa: E402  (сырой источник для перекрёстной сверки)

from core.data import load_ticker, load_risk_free, fmt_large  # noqa: E402
from core.dcf import run_dcf  # noqa: E402
from core.dcf_analysis import implied_growth, implied_return  # noqa: E402
from core.wacc import estimate_wacc  # noqa: E402

DEFAULT_BASKET = ["AAPL", "MSFT", "NVDA", "AMZN", "KO", "T", "JPM", "INTC", "TSLA"]
BROKEN_TICKER = "ZZZZXX"
# «Качественные» имена для жёстких проверок адекватности (умеренная бета,
# стабильный FCF). Высокобетные/сжигающие кэш проверяются мягко (⚠️).
QUALITY = {"AAPL", "MSFT", "KO", "T", "JPM"}

GROWTH_RATES = {"bear": 0.02, "base": 0.08, "bull": 0.15}
YEARS = 10

counts = {"✅": 0, "⚠️": 0, "❌": 0}


def report(mark, name, detail=""):
    counts[mark] += 1
    print(f"  {mark} {name}" + (f" — {detail}" if detail else ""))


def close(a, b, tol):
    return a is not None and b is not None and b != 0 and abs(a - b) / abs(b) <= tol


def in_range(x, lo, hi):
    return x is not None and lo <= x <= hi


def check_ticker(sym, rf):
    td = load_ticker(sym)
    if td is None:
        report("❌", f"{sym}: загрузка", "load_ticker вернул None")
        return
    print(f"\n=== {sym} · {td.name} · цена ${td.price:.2f} ===")
    raw = yf.Ticker(sym).info  # независимая сверка с сырым источником

    # ── 1. Согласованность данных ──────────────────────────────────────────
    eps = raw.get("trailingEps")
    if td.trailing_pe and eps and eps > 0:
        calc = td.price / eps
        mark = "✅" if close(td.trailing_pe, calc, 0.10) else "❌"
        report(mark, "P/E ≈ цена/EPS", f"{td.trailing_pe:.1f} vs {calc:.1f}")
    else:
        report("⚠️", "P/E ≈ цена/EPS", "нет EPS или P/E — пропуск")

    if td.market_cap and td.shares_outstanding:
        calc = td.price * td.shares_outstanding
        mark = "✅" if close(td.market_cap, calc, 0.05) else "❌"
        report(mark, "Кап-я ≈ цена×акции", f"{fmt_large(td.market_cap)} vs {fmt_large(calc)}")

    if td.enterprise_value and td.market_cap:
        calc = td.market_cap + td.net_debt
        mark = "✅" if close(td.enterprise_value, calc, 0.15) else "⚠️"
        report(mark, "EV ≈ кап-я + чистый долг",
               f"{fmt_large(td.enterprise_value)} vs {fmt_large(calc)}")

    for label, v in [("Gross Margin", td.gross_margins), ("Net Margin", td.profit_margins),
                     ("EBITDA Margin", td.ebitda_margins)]:
        if v is None:
            report("⚠️", f"{label}", "нет данных")
        else:
            report("✅" if -1.0 <= v <= 1.0 else "❌", f"{label} в [−100%,100%]", f"{v*100:.1f}%")

    if td.roe is not None:
        report("✅" if -3.0 <= td.roe <= 3.0 else "❌", "ROE разумный", f"{td.roe*100:.0f}%")

    dy = td.dividend_yield
    report("✅" if dy is None or 0 <= dy <= 0.15 else "❌", "Див. доходность в [0,15%]",
           "нет" if dy is None else f"{dy*100:.2f}%")

    if td.week52_low and td.week52_high:
        ok = td.week52_low * 0.98 <= td.price <= td.week52_high * 1.02
        report("✅" if ok else "❌", "Цена внутри 52w-диапазона",
               f"{td.week52_low:.0f} ≤ {td.price:.0f} ≤ {td.week52_high:.0f}")

    # ── 2. Логика модели ───────────────────────────────────────────────────
    try:
        cf = yf.Ticker(sym).cashflow
        if cf is not None and not cf.empty and "Free Cash Flow" in cf.index \
                and "Operating Cash Flow" in cf.index and "Capital Expenditure" in cf.index:
            col = cf.columns[0]
            fcf0, ocf0, capex0 = (cf.loc["Free Cash Flow"][col],
                                  cf.loc["Operating Cash Flow"][col],
                                  cf.loc["Capital Expenditure"][col])
            calc = ocf0 + capex0  # capex у Yahoo отрицательный
            mark = "✅" if close(fcf0, calc, 0.05) else "❌"
            report(mark, "FCF ≈ OCF − capex", f"{fmt_large(fcf0)} vs {fmt_large(calc)}")
    except Exception as e:
        report("⚠️", "FCF ≈ OCF − capex", f"не проверить: {e}")

    base = td.dcf_fcf_base(subtract_sbc=True)
    est = estimate_wacc(td.beta, rf, td.market_cap, td.total_debt)
    eff = est.wacc if est else 0.10

    if not base or base <= 0 or not td.shares_outstanding:
        # Компании без положительного FCF: модель обязана отказаться
        ig = implied_growth(price=td.price, fcf_base=base, shares=td.shares_outstanding,
                            net_debt=td.net_debt, wacc=eff, terminal_growth=0.025, years=YEARS)
        report("✅" if ig is None else "❌", "FCF≤0 → DCF корректно отказывается",
               f"база {fmt_large(base)}, implied_growth={'None' if ig is None else ig}")
        return

    if td.sbc_normalized:
        report("✅" if td.fcf_normalized_ex_sbc < td.fcf_normalized else "❌",
               "SBC уменьшает базу",
               f"{fmt_large(td.fcf_normalized_ex_sbc)} < {fmt_large(td.fcf_normalized)}")

    dcf = run_dcf(fcf_base=base, growth_rates=GROWTH_RATES, wacc=eff,
                  terminal_growth=0.025, years=YEARS,
                  shares=td.shares_outstanding, net_debt=td.net_debt)
    b, m, u = dcf["bear"].intrinsic, dcf["base"].intrinsic, dcf["bull"].intrinsic
    report("✅" if u >= m >= b else "❌", "Монотонность Bull ≥ Base ≥ Bear",
           f"{u:.0f} ≥ {m:.0f} ≥ {b:.0f}")
    report("✅" if dcf["base"].tv_share < 0.80 else "⚠️",
           f"TV-доля Base < 80% при {YEARS} годах", f"{dcf['base'].tv_share*100:.0f}%")

    fair = m
    ig_rt = implied_growth(price=fair, fcf_base=base, shares=td.shares_outstanding,
                           net_debt=td.net_debt, wacc=eff, terminal_growth=0.025, years=YEARS)
    ok = ig_rt is not None and abs(ig_rt - 0.08) < 1e-3
    report("✅" if ok else "❌", "Round-trip реверс-DCF (8%)",
           "None" if ig_rt is None else f"{ig_rt*100:.2f}%")

    # ── 3. Адекватность (дефолты: auto-WACC, 10 лет, SBC on) ───────────────
    strict = sym in QUALITY
    wacc_txt = f"WACC {eff*100:.1f}%" + ("" if est else " (фолбэк)")

    ig = implied_growth(price=td.price, fcf_base=base, shares=td.shares_outstanding,
                        net_debt=td.net_debt, wacc=eff, terminal_growth=0.025, years=YEARS)
    if ig is None:
        report("❌" if strict else "⚠️", f"Заложенный рост ({wacc_txt})",
               "вне диапазона −50..100%")
    else:
        ok = in_range(ig, -0.10, 0.40)
        mark = "✅" if ok else ("❌" if strict else "⚠️")
        report(mark, f"Заложенный рост в [−10%,40%] ({wacc_txt})", f"{ig*100:.1f}%")

    mult = (m * td.shares_outstanding) / base
    ok = in_range(mult, 10, 45)
    report("✅" if ok else ("❌" if strict else "⚠️"),
           "Мультипликатор Base в [10x,45x] FCF", f"{mult:.1f}x")

    ir = implied_return(price=td.price, fcf_base=base, shares=td.shares_outstanding,
                        net_debt=td.net_debt, growth_start=0.08,
                        terminal_growth=0.025, years=YEARS)
    if ir is None:
        report("⚠️", "Ожидаемая доходность", "не определяется")
    else:
        ok = in_range(ir, 0.02, 0.12)
        report("✅" if ok else ("❌" if strict else "⚠️"),
               "Ожидаемая доходность в [2%,12%]", f"{ir*100:.1f}%")

    # ── 4. Актуальность ────────────────────────────────────────────────────
    if td.history is not None and not td.history.empty:
        last = td.history.index[-1].to_pydatetime().replace(tzinfo=None)
        age = (datetime.datetime.now() - last).days
        report("✅" if age <= 5 else "❌", "Цена свежая (≤5 календ. дней)", f"{age} дн.")
    if td.financials is not None and not td.financials.empty:
        latest = max(td.financials.columns)
        age = (datetime.datetime.now() - latest.to_pydatetime().replace(tzinfo=None)).days
        report("✅" if age <= 548 else "⚠️", "Отчётность ≤ 18 мес.", f"{age} дн.")


def main():
    basket = sys.argv[1:] or DEFAULT_BASKET
    rf, rf_live = load_risk_free()
    print(f"Безрисковая ставка: {rf*100:.2f}% ({'живая ^TNX' if rf_live else 'фолбэк'})")
    report("✅" if in_range(rf, 0.01, 0.10) else "❌", "rf в разумном диапазоне")

    for sym in basket:
        try:
            check_ticker(sym, rf)
        except Exception as e:
            report("❌", f"{sym}: НЕОЖИДАННОЕ ИСКЛЮЧЕНИЕ", repr(e))

    print(f"\n=== {BROKEN_TICKER} (битый тикер) ===")
    td = load_ticker(BROKEN_TICKER)
    report("✅" if td is None else "❌", "Битый тикер → аккуратный None")

    print(f"\nИтого: {counts['✅']} ✅ · {counts['⚠️']} ⚠️ · {counts['❌']} ❌")
    sys.exit(1 if counts["❌"] else 0)


if __name__ == "__main__":
    main()
