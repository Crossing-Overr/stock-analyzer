#!/usr/bin/env python3
"""
Прогоняет тикеры из data/sp500.txt через модель и пишет data/sp500_snapshot.json.

Запуск:  python3 scripts/build_snapshot.py            # все из sp500.txt
         python3 scripts/build_snapshot.py AAPL MSFT  # только эти (для теста)

Устойчив к обрывам: доливает в существующий снимок, пропускает уже посчитанные.
Долгий (~15 мин на 500 тикеров) — это норма, идёт throttling ради Yahoo.
"""
import datetime
import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

# Позволяет запускать как `python3 scripts/build_snapshot.py` из корня репо:
# по умолчанию Python кладёт в sys.path[0] папку scripts/, а не корень,
# так что "import core" без этого не находится.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.data import load_ticker, load_risk_free  # noqa: E402
from core.dcf import run_dcf  # noqa: E402
from core.dcf_analysis import implied_growth, implied_return  # noqa: E402
from core.wacc import estimate_wacc  # noqa: E402

HERE = os.path.dirname(__file__)
LIST = os.path.join(HERE, "..", "data", "sp500.txt")
OUT = os.path.join(HERE, "..", "data", "sp500_snapshot.json")

GROWTH = {"bear": 0.02, "base": 0.08, "bull": 0.15}
YEARS = 10
TG = 0.025
THROTTLE = 0.7   # пауза между тикерами, сек


def read_symbols():
    if len(sys.argv) > 1:
        return [s.upper() for s in sys.argv[1:]]
    with open(LIST, encoding="utf-8") as fh:
        return [ln.strip().upper() for ln in fh if ln.strip()]


def load_existing():
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as fh:
                data = json.load(fh)
            return {r["symbol"]: r for r in data.get("tickers", [])}
        except Exception:
            pass
    return {}


def compute(sym, rf):
    td = load_ticker(sym)
    if td is None or td.price is None:
        return None
    base = td.dcf_fcf_base(subtract_sbc=True)
    est = estimate_wacc(td.beta, rf, td.market_cap, td.total_debt)
    wacc = est.wacc if est else 0.10
    applicable = bool(base and base > 0 and td.shares_outstanding)

    row = dict(
        symbol=sym, name=td.name, sector=td.sector, price=td.price,
        market_cap=td.market_cap, pe=td.trailing_pe, fcf_base=base,
        fcf_positive=bool(base and base > 0), wacc=wacc,
        revenue_growth=td.revenue_growth, roe=td.roe, net_margin=td.profit_margins,
        dcf_applicable=applicable,
        upside_base=None, implied_growth=None, implied_return=None,
        fcf_multiple=None, price_pct_of_52w_range=None,
    )
    if td.week52_high and td.week52_low and td.week52_high > td.week52_low:
        row["price_pct_of_52w_range"] = (td.price - td.week52_low) / (td.week52_high - td.week52_low)
    if applicable:
        dcf = run_dcf(fcf_base=base, growth_rates=GROWTH, wacc=wacc,
                      terminal_growth=TG, years=YEARS,
                      shares=td.shares_outstanding, net_debt=td.net_debt)
        iv = dcf["base"].intrinsic
        row["upside_base"] = (iv - td.price) / td.price * 100 if iv > 0 else None
        row["implied_growth"] = implied_growth(
            price=td.price, fcf_base=base, shares=td.shares_outstanding,
            net_debt=td.net_debt, wacc=wacc, terminal_growth=TG, years=YEARS)
        row["implied_return"] = implied_return(
            price=td.price, fcf_base=base, shares=td.shares_outstanding,
            net_debt=td.net_debt, growth_start=GROWTH["base"], terminal_growth=TG, years=YEARS)
        if td.market_cap:
            row["fcf_multiple"] = td.market_cap / base
    return row


def save(rows_by_sym, rf):
    rows = list(rows_by_sym.values())
    data = {"as_of": datetime.date.today().isoformat(), "rf": rf,
            "count": len(rows), "tickers": rows}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)


def main():
    symbols = read_symbols()
    done = load_existing()
    rf, rf_live = load_risk_free()
    print(f"rf: {rf*100:.2f}% ({'живая' if rf_live else 'фолбэк'}) · "
          f"{len(symbols)} тикеров · уже посчитано {len(done)}")

    for i, sym in enumerate(symbols, 1):
        if sym in done:
            continue
        try:
            row = compute(sym, rf)
            if row is not None:
                done[sym] = row
                mark = "✓" if row["dcf_applicable"] else "○"
                print(f"[{i}/{len(symbols)}] {mark} {sym}")
            else:
                print(f"[{i}/{len(symbols)}] ✗ {sym} (нет данных)")
        except Exception as e:
            print(f"[{i}/{len(symbols)}] ✗ {sym} ошибка: {e}")
        if i % 25 == 0:            # периодически сохраняем прогресс
            save(done, rf)
        time.sleep(THROTTLE)

    save(done, rf)
    applicable = sum(1 for r in done.values() if r["dcf_applicable"])
    print(f"\nГотово: {len(done)} записей, из них с DCF: {applicable}. → {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
