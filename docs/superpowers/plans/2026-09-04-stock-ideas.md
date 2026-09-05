# Stock Ideas (Curated Picks) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Новая вкладка «💎 Идеи» — курируемая подборка акций S&P 500 через 5 пресетов + тонкую настройку, работающая мгновенно на предпосчитанном снимке.

**Architecture:** `scripts/build_snapshot.py` прогоняет S&P 500 через существующие core-модули и пишет `data/sp500_snapshot.json` (коммитится). `core/screener.py` — чистая тестируемая логика (пресеты, фильтры, сортировка) поверх снимка. `pages/4_💎_Идеи.py` рисует чипы пресетов и карточки; клик открывает Анализ. Приложение к Yahoo для подборки не обращается.

**Tech Stack:** Python 3.9, Streamlit, yfinance (только в скрипте сборки), pandas (для списка S&P), pytest.

**Спека:** `docs/superpowers/specs/2026-09-04-stock-ideas-design.md`

**Окружение:** `pip`/`streamlit`/`pytest` НЕ в PATH — только `python3 -m`. Python 3.9 → `Optional[...]`, НЕ `X | None`. В `st.caption`/`st.info` парные `$` = LaTeX → текст с `fmt_large(...)` экранировать `.replace("$", "\\$")`; в сырых HTML-блоках не нужно.

---

## Файловая структура

```
data/
├── sp500.txt              # НОВЫЙ: список тикеров S&P 500, по одному в строке
├── sp500_snapshot.json    # НОВЫЙ: предпосчитанный снимок (коммитится)
core/
├── screener.py            # НОВЫЙ: пресеты, фильтры, screen() — чистая логика
scripts/
├── fetch_sp500.py         # НОВЫЙ: генерит data/sp500.txt (запуск разово)
├── build_snapshot.py      # НОВЫЙ: прогон S&P 500 → snapshot.json
pages/
└── 4_💎_Идеи.py            # НОВЫЙ: вкладка подборки
tests/
└── test_screener.py       # НОВЫЙ
```

**Границы:** `core/screener.py` не знает про Streamlit/yfinance (только json + логика). `build_snapshot.py` переиспользует уже протестированные core-модули.

---

## Task 1: `core/screener.py` — пресеты, фильтры, screen() (TDD)

**Files:**
- Create: `core/screener.py`
- Test: `tests/test_screener.py`

- [ ] **Step 1: Написать падающие тесты — `tests/test_screener.py`**

```python
from core.screener import screen, ScreenFilters, PRESETS, load_snapshot


def _snapshot():
    """Синтетический снимок, покрывающий каждый пресет + мусор, который обязан
    отсеиваться. rf=0.045."""
    def row(sym, **kw):
        base = dict(symbol=sym, name=sym + " Inc.", sector="Tech", price=100.0,
                    market_cap=1e11, pe=20.0, fcf_base=5e9, fcf_positive=True,
                    fcf_multiple=15.0, wacc=0.10, upside_base=10.0,
                    implied_growth=0.05, implied_return=0.06, revenue_growth=0.10,
                    roe=0.20, net_margin=0.15, price_pct_of_52w_range=0.6,
                    dcf_applicable=True)
        base.update(kw)
        return base

    return {
        "as_of": "2026-09-04", "rf": 0.045, "count": 9,
        "tickers": [
            row("CHEAP", upside_base=60.0, pe=15.0, fcf_multiple=10.0),   # явный лидер undervalued
            row("UND",  upside_base=30.0, pe=20.0),                       # недооценённая
            row("GROW", implied_growth=0.03, revenue_growth=0.20,
                        fcf_multiple=12.0, roe=0.16),                     # рост дёшево (gap 0.17)
            row("QUAL", roe=0.30, net_margin=0.25, upside_base=-5.0, pe=28.0),  # качество со скидкой
            row("RET",  implied_return=0.11, upside_base=5.0, roe=0.14, net_margin=0.11),  # доходность
            # TURN/JUNK: высокий P/E (45), чтобы не попадали в undervalued (pe<30);
            # turnaround pe не проверяет.
            row("TURN", price_pct_of_52w_range=0.1, upside_base=40.0, pe=45.0,
                        revenue_growth=-0.08, roe=0.22, net_margin=0.13),  # turnaround
            row("JUNK", price_pct_of_52w_range=0.1, upside_base=40.0, pe=45.0,
                        revenue_growth=-0.10, roe=0.05, net_margin=0.04),  # падающий нож — отсеять
            row("BANK", dcf_applicable=False),                            # DCF неприменим
            row("NEG",  fcf_positive=False),                             # отрицательный FCF
        ],
    }


def _syms(result):
    return [r["symbol"] for r in result.rows]


def test_all_presets_exist():
    assert set(PRESETS) == {"undervalued", "growth_cheap", "quality_discount",
                            "high_return", "turnaround"}


def test_bank_and_negfcf_never_appear():
    snap = _snapshot()
    for pid in PRESETS:
        syms = _syms(screen(snap, pid, ScreenFilters()))
        assert "BANK" not in syms
        assert "NEG" not in syms


def test_undervalued_keeps_positive_upside_cheap_pe_sorted():
    snap = _snapshot()
    res = screen(snap, "undervalued", ScreenFilters())
    syms = _syms(res)
    assert "QUAL" not in syms          # upside -5 → нужен upside>0
    assert "TURN" not in syms          # pe 45 → не проходит pe<30
    assert res.rows[0]["symbol"] == "CHEAP"        # макс. апсайд 60 сверху
    assert res.total_passed == len(res.rows)


def test_growth_cheap_ranks_by_gap():
    snap = _snapshot()
    res = screen(snap, "growth_cheap", ScreenFilters())
    # GROW: gap 0.20-0.03=0.17, лучший
    assert res.rows[0]["symbol"] == "GROW"


def test_quality_discount_requires_roe_and_margin():
    snap = _snapshot()
    syms = _syms(screen(snap, "quality_discount", ScreenFilters()))
    assert "QUAL" in syms       # roe0.30, margin0.25, upside-5>-10
    assert "RET" not in syms    # roe0.14<0.15


def test_high_return_beats_riskfree():
    snap = _snapshot()
    res = screen(snap, "high_return", ScreenFilters())
    assert res.rows[0]["symbol"] == "RET"          # 0.11 > rf 0.045, максимум


def test_turnaround_selects_beaten_down_with_fundamentals_and_flags_risk():
    snap = _snapshot()
    res = screen(snap, "turnaround", ScreenFilters())
    syms = _syms(res)
    assert "TURN" in syms       # дёшево + фундамент выше медианы
    assert "JUNK" not in syms   # дёшево, но roe/margin ниже медианы
    assert all(r.get("badge") == "risk" for r in res.rows)


def test_user_filters_tighten_on_top_of_preset():
    snap = _snapshot()
    res = screen(snap, "undervalued", ScreenFilters(min_upside=35.0))
    # min_upside=35 отсекает UND (30); остаётся CHEAP (60) — единственный с upside>=35 и pe<30
    assert _syms(res) == ["CHEAP"]
    assert all(r["upside_base"] >= 35.0 for r in res.rows)
    assert "UND" not in _syms(res)


def test_empty_result_is_safe():
    snap = _snapshot()
    res = screen(snap, "undervalued", ScreenFilters(min_upside=999.0))
    assert res.rows == []
    assert res.total_passed == 0


def test_limit_caps_rows():
    snap = _snapshot()
    res = screen(snap, "undervalued", ScreenFilters(), limit=1)
    assert len(res.rows) == 1
    assert res.total_passed >= 1     # total не обрезается лимитом
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python3 -m pytest tests/test_screener.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.screener'`

- [ ] **Step 3: Реализовать `core/screener.py`**

```python
import json
import statistics
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ScreenFilters:
    """Тонкая настройка поверх пресета. None = ограничение выключено."""
    min_upside: Optional[float] = None            # % (upside_base)
    max_pe: Optional[float] = None
    min_revenue_growth: Optional[float] = None    # доля (0.05 = 5%)


@dataclass
class Preset:
    id: str
    label: str
    describe: str
    predicate: Callable      # (row, ctx) -> bool
    sort_key: Callable       # row -> число (по убыванию)
    badge: Optional[str] = None


@dataclass
class ScreenResult:
    as_of: str
    total_passed: int
    rows: list


def _num(row, key):
    v = row.get(key)
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


# ─── Предикаты пресетов ──────────────────────────────────────────────────────
def _p_undervalued(r, c):
    up, pe = _num(r, "upside_base"), _num(r, "pe")
    return up is not None and up > 0 and pe is not None and pe < 30


def _p_growth_cheap(r, c):
    ig, rg, mult = _num(r, "implied_growth"), _num(r, "revenue_growth"), _num(r, "fcf_multiple")
    return (ig is not None and rg is not None and ig < rg
            and mult is not None and mult < 20)


def _p_quality_discount(r, c):
    roe, nm, up = _num(r, "roe"), _num(r, "net_margin"), _num(r, "upside_base")
    return (roe is not None and roe > 0.15 and nm is not None and nm > 0.10
            and up is not None and up > -10)


def _p_high_return(r, c):
    ir = _num(r, "implied_return")
    return ir is not None and ir > c["rf"]


def _p_turnaround(r, c):
    pct, up, rg = (_num(r, "price_pct_of_52w_range"), _num(r, "upside_base"),
                   _num(r, "revenue_growth"))
    roe, nm = _num(r, "roe"), _num(r, "net_margin")
    if None in (pct, up, rg):
        return False
    beaten = pct < 0.33
    reward = up > 30
    slowing = rg < 0.05
    fundamentals = ((roe is not None and roe > c["median_roe"])
                    or (nm is not None and nm > c["median_margin"]))
    return beaten and reward and slowing and fundamentals


PRESETS = {
    "undervalued": Preset(
        "undervalued", "💎 Недооценённые с FCF",
        "Дёшево относительно денежного потока: апсайд DCF > 0, P/E < 30.",
        _p_undervalued, lambda r: _num(r, "upside_base") or -1e9),
    "growth_cheap": Preset(
        "growth_cheap", "🚀 Рост за небольшие деньги",
        "Рынок закладывает рост ниже фактического, мультипликатор FCF < 20x.",
        _p_growth_cheap,
        lambda r: (_num(r, "revenue_growth") or 0) - (_num(r, "implied_growth") or 0)),
    "quality_discount": Preset(
        "quality_discount", "🏆 Качество со скидкой",
        "Сильный бизнес (ROE>15%, маржа>10%) без завышенной цены.",
        _p_quality_discount,
        lambda r: (_num(r, "roe") or 0) + (_num(r, "upside_base") or 0) / 100),
    "high_return": Preset(
        "high_return", "💰 Высокая доходность",
        "Ожидаемая годовая доходность выше безрисковой ставки.",
        _p_high_return, lambda r: _num(r, "implied_return") or -1e9),
    "turnaround": Preset(
        "turnaround", "🔄 Turnaround",
        "Распродана, но фундамент ещё жив и большой апсайд. Максимальный риск.",
        _p_turnaround, lambda r: _num(r, "upside_base") or -1e9, badge="risk"),
}


def _passes_filters(r, f: ScreenFilters):
    if f.min_upside is not None:
        up = _num(r, "upside_base")
        if up is None or up < f.min_upside:
            return False
    if f.max_pe is not None:
        pe = _num(r, "pe")
        if pe is None or pe > f.max_pe:
            return False
    if f.min_revenue_growth is not None:
        rg = _num(r, "revenue_growth")
        if rg is None or rg < f.min_revenue_growth:
            return False
    return True


def load_snapshot(path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def screen(snapshot: dict, preset_id: str, filters: Optional[ScreenFilters] = None,
           limit: int = 20) -> ScreenResult:
    """Применяет пресет + фильтры к снимку, ранжирует, отдаёт топ-limit."""
    filters = filters or ScreenFilters()
    preset = PRESETS[preset_id]

    # Глобальный префильтр: только применимые к FCF-DCF, положительный FCF.
    base = [r for r in snapshot.get("tickers", [])
            if r.get("dcf_applicable") and r.get("fcf_positive")]

    roes = [r["roe"] for r in base if _num(r, "roe") is not None]
    margins = [r["net_margin"] for r in base if _num(r, "net_margin") is not None]
    ctx = {
        "rf": snapshot.get("rf", 0.045),
        "median_roe": statistics.median(roes) if roes else 0.0,
        "median_margin": statistics.median(margins) if margins else 0.0,
    }

    passed = [r for r in base
              if preset.predicate(r, ctx) and _passes_filters(r, filters)]
    passed.sort(key=preset.sort_key, reverse=True)

    rows = [dict(r, badge=preset.badge) for r in passed[:limit]]
    return ScreenResult(as_of=snapshot.get("as_of", ""),
                        total_passed=len(passed), rows=rows)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `python3 -m pytest tests/test_screener.py -q`
Expected: PASS (10 passed)

- [ ] **Step 5: Полная сюита**

Run: `python3 -m pytest -q`
Expected: `82 passed` (72 существующих + 10 новых)

- [ ] **Step 6: Commit**

```bash
git add core/screener.py tests/test_screener.py
git commit -m "feat: screener — 5 presets, filters, ranking over snapshot"
```

---

## Task 2: `scripts/fetch_sp500.py` → `data/sp500.txt`

**Files:**
- Create: `scripts/fetch_sp500.py`, `data/sp500.txt` (сгенерированный)

- [ ] **Step 1: Создать `scripts/fetch_sp500.py`**

```python
#!/usr/bin/env python3
"""
Генерирует data/sp500.txt — список тикеров S&P 500 с Википедии.
Запуск разово (и когда состав индекса заметно поменяется):
    python3 scripts/fetch_sp500.py
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "sp500.txt")


def main():
    try:
        tables = pd.read_html(URL)
    except Exception as e:
        print(f"❌ Не удалось получить список с Википедии: {e}")
        print("Проверь интернет или скачай список вручную в data/sp500.txt.")
        sys.exit(1)

    df = tables[0]
    col = "Symbol" if "Symbol" in df.columns else df.columns[0]
    # yfinance хочет BRK-B вместо BRK.B
    symbols = [str(s).strip().upper().replace(".", "-") for s in df[col] if str(s).strip()]
    symbols = sorted(set(symbols))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(symbols) + "\n")
    print(f"✅ Записано {len(symbols)} тикеров в {os.path.normpath(OUT)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Запустить и проверить**

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 scripts/fetch_sp500.py 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn" && echo "=== первые строки ===" && head -5 data/sp500.txt && wc -l data/sp500.txt
```
Expected: «Записано ~500 тикеров», файл на ~500 строк. Если Википедия недоступна — СТОП, доложить контроллеру (он даст запасной список), не выдумывать тикеры.

- [ ] **Step 3: Commit**

```bash
git add scripts/fetch_sp500.py data/sp500.txt
git commit -m "feat: fetch_sp500.py + generated S&P 500 ticker list"
```

---

## Task 3: `scripts/build_snapshot.py`

**Files:**
- Create: `scripts/build_snapshot.py`

- [ ] **Step 1: Создать `scripts/build_snapshot.py`**

```python
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
```

- [ ] **Step 2: Проверить на маленьком списке**

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 scripts/build_snapshot.py AAPL MSFT KO JPM INTC 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn|No runtime" && echo "=== snapshot ===" && python3 -c "import json; d=json.load(open('data/sp500_snapshot.json')); print('as_of',d['as_of'],'rf',d['rf'],'count',d['count']); [print(r['symbol'],'dcf' if r['dcf_applicable'] else 'no-dcf','upside',r['upside_base']) for r in d['tickers']]"
```
Expected: AAPL/MSFT/KO с DCF и апсайдом, JPM/INTC — `dcf_applicable=false`. Файл валидный JSON с `as_of`/`rf`.

- [ ] **Step 3: Commit (только скрипт; настоящий полный снимок — Task 5)**

```bash
git add scripts/build_snapshot.py
git commit -m "feat: build_snapshot.py — S&P 500 → snapshot.json (resumable, throttled)"
```

---

## Task 4: `pages/4_💎_Идеи.py` — вкладка подборки

**Files:**
- Create: `pages/4_💎_Идеи.py`

- [ ] **Step 1: Создать страницу `pages/4_💎_Идеи.py`**

Карточка — сырой HTML через `st.markdown(..., unsafe_allow_html=True)` (в нём `$` безопасен, экранировать не надо); клик по тикеру — отдельная маленькая кнопка «Анализ →» рядом, потому что в HTML-блок кнопку Streamlit встроить нельзя.

```python
import os
import streamlit as st

from core.data import fmt_large
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
    st.caption("Только положительный FCF — всегда включено (без него DCF бессмысленен).")

filters = ScreenFilters(min_upside=float(min_up), max_pe=float(max_pe),
                        min_revenue_growth=min_rg / 100)
res = screen(snap, st.session_state.preset, filters, limit=20)

st.caption(f"Данные на {res.as_of} · **{res.total_passed}** компаний прошло фильтр · "
           f"показаны топ-{len(res.rows)}")

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
```

- [ ] **Step 2: Приём тикера на вкладке Анализ**

В `pages/1_📊_Анализ.py` найти строку с `st.text_input("Тикер", value="AAPL", ...)` и заменить `value="AAPL"` на подхват префилла:

```python
_prefill = st.session_state.pop("ticker_prefill", "AAPL")
ticker = st.text_input("Тикер", value=_prefill,
                       placeholder="AAPL, MSFT, NVDA...").upper().strip()
```

- [ ] **Step 3: Проверить**

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -m py_compile "pages/4_💎_Идеи.py" "pages/1_📊_Анализ.py" && echo "compile ok" && python3 -m pytest -q 2>&1 | tail -1
```
Expected: `compile ok`, `82 passed`

Run (AppTest — снимок из мини-прогона Task 3 уже есть):
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -c "
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('pages/4_💎_Идеи.py', default_timeout=60)
at.run()
print('exception:', bool(at.exception))
if at.exception: print(at.exception)
print('кнопок-пресетов:', len([b for b in at.button if 'preset_' in (b.key or '')]))
" 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn|No runtime|ScriptRunContext"
```
Expected: `exception: False`, 5 кнопок-пресетов.

- [ ] **Step 4: Commit**

```bash
git add "pages/4_💎_Идеи.py" "pages/1_📊_Анализ.py"
git commit -m "feat: Ideas page — preset picks with cards, click-through to Analysis"
```

---

## Task 5: Полный снимок S&P 500, проверка, доки (выполняет контроллер)

Долгий сетевой прогон — запускает контроллер, НЕ субагент.

**Files:**
- Create/update: `data/sp500_snapshot.json`
- Modify: `CLAUDE.md`, `README.md`

- [ ] **Step 1: Построить полный снимок**

Run: `cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 scripts/build_snapshot.py`
(~15 мин; устойчив к обрыву — при падении перезапустить, дольёт.)
Expected: «Готово: ~500 записей, из них с DCF: ~350».

- [ ] **Step 2: Прогнать подборку и глазами проверить адекватность**

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -c "
from core.screener import load_snapshot, screen, ScreenFilters, PRESETS
snap = load_snapshot('data/sp500_snapshot.json')
for pid in PRESETS:
    res = screen(snap, pid, ScreenFilters(), limit=5)
    print(f'\n=== {PRESETS[pid].label} ({res.total_passed}) ===')
    for r in res.rows:
        print(f\"  {r['symbol']:6} upside {r.get('upside_base')}  pe {r.get('pe')}  rev {r.get('revenue_growth')}\")
"
```
Ожидание: у каждого пресета осмысленные тикеры (не мусор), turnaround — распроданные имена. Явные аномалии доложить контроллеру перед коммитом снимка.

- [ ] **Step 3: Обновить `CLAUDE.md` и `README.md`**

В `CLAUDE.md` в списке `pages/` добавить строку про `Идеи`, и раздел:

```markdown
### Подборка идей (`core/screener.py`, `scripts/build_snapshot.py`)

- Вкладка «💎 Идеи» — курируемая подборка S&P 500 по 5 пресетам (недооценённые,
  рост дёшево, качество со скидкой, высокая доходность, turnaround) + фильтры.
- Работает на предпосчитанном снимке `data/sp500_snapshot.json` (не живой скан).
- Обновить: `python3 scripts/build_snapshot.py` (~15 мин) + git push.
  Список тикеров: `python3 scripts/fetch_sp500.py`.
```

В `README.md` — добавить вкладку «💎 Идеи» в список и в раздел структуры.

- [ ] **Step 4: Финальная проверка и commit**

Run: `python3 -m pytest -q 2>&1 | tail -1`
Expected: `82 passed`

```bash
git add data/sp500_snapshot.json CLAUDE.md README.md
git commit -m "feat: build full S&P 500 snapshot; document Ideas tab"
```

- [ ] **Step 5: НЕ пушить без разрешения владельца**

**СТОП:** `git push` = автодеплой публичного приложения. Только с явного «пуш».

---

## Задел на будущее (НЕ сейчас — YAGNI)

- Автообновление снимка (нужен планировщик — нет на free Streamlit Cloud).
- Секторные фильтры и сортировки в подборке.
- Пометка «снимок устарел > 30 дней».
- Сохранение приглянувшихся идей в Избранное одной кнопкой.
