# Stock Analysator v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Разбить монолитный `app.py` на модули, добавить кэш, три вкладки (Анализ / Сравнение / Избранное) с локальным избранным в браузере, и подготовить к деплою на Streamlit Community Cloud.

**Architecture:** Чистые Python-модули в `core/` (данные, DCF, сравнение, избранное) отделены от отрисовки в `ui/`. Streamlit multipage: `app.py` — вход + сайдбар, `pages/` — три экрана. Логика тестируется через pytest; UI проверяется запуском приложения.

**Tech Stack:** Python, Streamlit (multipage), yfinance, plotly, pandas, numpy, streamlit-local-storage, pytest.

---

## Файловая структура (что за что отвечает)

```
stock-analysator/
├── app.py                     # вход: конфиг страницы + сайдбар с DCF-слайдерами
├── pages/
│   ├── 1_📊_Анализ.py          # один тикер: метрики + график + DCF (текущий экран)
│   ├── 2_⚖️_Сравнение.py       # таблица «тикеры × метрики» + апсайд Base
│   └── 3_⭐_Избранное.py        # список из localStorage
├── core/
│   ├── __init__.py
│   ├── data.py                # safe(), форматтеры, TickerData, load_ticker()
│   ├── dcf.py                 # run_dcf() — чистая математика
│   ├── compare.py             # build_comparison_table()
│   └── favorites.py           # get/add/remove поверх localStorage + чистые хелперы
├── ui/
│   ├── __init__.py
│   ├── theme.py               # CSS + inject_theme()
│   ├── sidebar.py             # render_sidebar() → DcfParams
│   └── components.py          # scenario_card, price_chart, dcf_charts, financials_chart
├── tests/
│   ├── test_dcf.py
│   ├── test_data.py
│   ├── test_compare.py
│   └── test_favorites.py
├── requirements.txt
├── .gitignore
└── README.md
```

**Boundaries:**
- `core/` не импортирует `ui/` и не рисует ничего Streamlit-специфичного (кроме `@st.cache_data` в `load_ticker`, который безвреден для тестов, т.к. тестируем чистый билдер `TickerData.from_info`).
- `ui/` не знает про yfinance — работает только с `TickerData` и `ScenarioResult`.
- Страницы в `pages/` только собирают вызовы `core` + `ui`.

---

## Task 1: Скелет проекта, зависимости, pytest

**Files:**
- Create: `requirements.txt`, `.gitignore`, `core/__init__.py`, `ui/__init__.py`, `tests/__init__.py`
- Create: `pytest.ini`

- [ ] **Step 1: Создать `requirements.txt`**

```
streamlit>=1.36
yfinance>=0.2.40
plotly>=5.22
pandas>=2.2
numpy>=1.26
streamlit-local-storage>=0.1.5
pytest>=8.0
```

- [ ] **Step 2: Создать `.gitignore`**

```
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/
.DS_Store
.streamlit/secrets.toml
```

- [ ] **Step 3: Создать пустые пакеты**

Создать `core/__init__.py`, `ui/__init__.py`, `tests/__init__.py` — пустые файлы.

- [ ] **Step 4: Создать `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

- [ ] **Step 5: Установить зависимости и проверить pytest**

Run: `pip install -r requirements.txt && pytest -q`
Expected: `no tests ran` (0 тестов, без ошибок импорта).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .gitignore core/__init__.py ui/__init__.py tests/__init__.py pytest.ini
git commit -m "chore: project skeleton, deps, pytest setup"
```

---

## Task 2: `core/dcf.py` — чистая DCF-математика (TDD)

Рефакторим текущий `run_dcf`: убираем цвета/эмодзи (это UI), ключи сценариев — строки `"bear"/"base"/"bull"`, результат — dataclass `ScenarioResult`. Добавляем защиту от `wacc <= terminal_growth` (деление на ноль в модели Гордона).

**Files:**
- Create: `core/dcf.py`
- Test: `tests/test_dcf.py`

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_dcf.py
import math
from core.dcf import run_dcf, ScenarioResult

BASE = dict(
    fcf_base=100.0,
    wacc=0.10,
    terminal_growth=0.0,
    years=1,
    shares=10.0,
    net_debt=0.0,
)

def test_golden_single_year_zero_growth():
    # y1: fcf=100, pv=100/1.1=90.909; TV=100/(0.1-0)=1000, pv_tv=1000/1.1=909.09
    # EV=1000, equity=1000, intrinsic=100, tv_share=0.9090909
    res = run_dcf(growth_rates={"bear": 0.0, "base": 0.0, "bull": 0.0}, **BASE)
    r = res["base"]
    assert isinstance(r, ScenarioResult)
    assert math.isclose(r.enterprise_value, 1000.0, rel_tol=1e-9)
    assert math.isclose(r.intrinsic, 100.0, rel_tol=1e-9)
    assert math.isclose(r.tv_share, 909.0909090909091 / 1000.0, rel_tol=1e-9)

def test_net_debt_reduces_equity():
    res = run_dcf(growth_rates={"bear": 0.0, "base": 0.0, "bull": 0.0},
                  **{**BASE, "net_debt": 200.0})
    assert math.isclose(res["base"].intrinsic, 80.0, rel_tol=1e-9)

def test_higher_growth_gives_higher_value():
    res = run_dcf(growth_rates={"bear": 0.0, "base": 0.08, "bull": 0.20},
                  **{**BASE, "years": 5})
    assert res["bull"].intrinsic > res["base"].intrinsic > res["bear"].intrinsic

def test_growth_fades_to_terminal():
    res = run_dcf(growth_rates={"bear": 0.0, "base": 0.20, "bull": 0.0},
                  **{**BASE, "years": 5, "terminal_growth": 0.02})
    path = res["base"].growth_path
    assert math.isclose(path[0], 0.20, rel_tol=1e-9)      # 1-й год = стартовый
    assert math.isclose(path[-1], 0.02, rel_tol=1e-9)     # последний = терминальный
    assert len(path) == 5

def test_wacc_not_greater_than_terminal_is_guarded():
    # wacc == terminal → без защиты деление на ноль; ждём конечное число
    res = run_dcf(growth_rates={"bear": 0.05, "base": 0.05, "bull": 0.05},
                  **{**BASE, "wacc": 0.05, "terminal_growth": 0.05, "years": 3})
    assert math.isfinite(res["base"].intrinsic)

def test_zero_shares_gives_zero_intrinsic():
    res = run_dcf(growth_rates={"bear": 0.0, "base": 0.0, "bull": 0.0},
                  **{**BASE, "shares": 0.0})
    assert res["base"].intrinsic == 0.0
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_dcf.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.dcf'`.

- [ ] **Step 3: Реализовать `core/dcf.py`**

```python
# core/dcf.py
from dataclasses import dataclass


@dataclass
class ScenarioResult:
    growth_start: float
    growth_path: list[float]
    fcfs_pv: list[float]
    pv_terminal: float
    enterprise_value: float
    equity_value: float
    intrinsic: float
    tv_share: float


def run_dcf(fcf_base, growth_rates, wacc, terminal_growth, years, shares, net_debt):
    """
    2-фазная DCF с линейным затуханием роста.

    Рост в 1-й год = стартовый (из growth_rates), к последнему году линейно
    спадает к terminal_growth. Это убирает нереалистичное компаундирование и
    не даёт терминальной стоимости раздувать оценку.

    growth_rates: dict {"bear": float, "base": float, "bull": float} —
        стартовые годовые темпы роста FCF.
    Возвращает dict {name: ScenarioResult}.
    """
    # Модель Гордона требует wacc > terminal_growth. Защищаемся от деления
    # на ноль/отрицательного знаменателя, слегка поджимая терминальный рост.
    eff_terminal = min(terminal_growth, wacc - 1e-3)

    results = {}
    for name, g_start in growth_rates.items():
        fcf = fcf_base
        growth_path = []
        fcfs_pv = []
        for y in range(1, years + 1):
            if years > 1:
                g = g_start + (eff_terminal - g_start) * (y - 1) / (years - 1)
            else:
                g = g_start
            growth_path.append(g)
            fcf = fcf * (1 + g)
            fcfs_pv.append(fcf / (1 + wacc) ** y)

        terminal_fcf = fcf * (1 + eff_terminal)
        terminal_value = terminal_fcf / (wacc - eff_terminal)
        pv_terminal = terminal_value / (1 + wacc) ** years

        enterprise_value = sum(fcfs_pv) + pv_terminal
        equity_value = enterprise_value - net_debt
        intrinsic = equity_value / shares if shares > 0 else 0.0
        tv_share = pv_terminal / enterprise_value if enterprise_value > 0 else 0.0

        results[name] = ScenarioResult(
            growth_start=g_start,
            growth_path=growth_path,
            fcfs_pv=fcfs_pv,
            pv_terminal=pv_terminal,
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            intrinsic=intrinsic,
            tv_share=tv_share,
        )
    return results
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_dcf.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add core/dcf.py tests/test_dcf.py
git commit -m "feat: pure DCF module with growth-fade and Gordon guard"
```

---

## Task 3: `core/data.py` — TickerData, safe(), форматтеры (TDD)

**Files:**
- Create: `core/data.py`
- Test: `tests/test_data.py`

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_data.py
import pytest
from core.data import safe, fmt_large, fmt_pct, fmt_mult, TickerData

def test_safe_returns_default_for_none_nan_empty():
    assert safe({"x": None}, "x", "D") == "D"
    assert safe({"x": float("nan")}, "x", "D") == "D"
    assert safe({"x": "N/A"}, "x", "D") == "D"
    assert safe({"x": ""}, "x", "D") == "D"
    assert safe({}, "x", "D") == "D"

def test_safe_returns_value_when_present():
    assert safe({"x": 5}, "x") == 5
    assert safe({"x": "AAPL"}, "x") == "AAPL"

def test_fmt_large():
    assert fmt_large(2.5e12) == "$2.50T"
    assert fmt_large(3.1e9) == "$3.10B"
    assert fmt_large(4.2e6) == "$4.20M"
    assert fmt_large(500) == "$500"
    assert fmt_large(None) == "N/A"
    assert fmt_large(float("nan")) == "N/A"

def test_fmt_pct():
    assert fmt_pct(0.123) == "12.3%"
    assert fmt_pct(None) == "N/A"

def test_fmt_mult():
    assert fmt_mult(15.4) == "15.4x"
    assert fmt_mult(1.2, "") == "1.2"
    assert fmt_mult(None) == "N/A"

def test_tickerdata_from_info_extracts_and_computes_net_debt():
    info = {
        "longName": "Apple Inc.", "sector": "Technology", "currency": "USD",
        "currentPrice": 200.0, "previousClose": 195.0,
        "marketCap": 3.0e12, "totalDebt": 100.0, "totalCash": 40.0,
        "freeCashflow": 1.0e11, "sharesOutstanding": 1.5e10,
        "trailingPE": 30.0,
    }
    td = TickerData.from_info("AAPL", info, history=None, financials=None)
    assert td.name == "Apple Inc."
    assert td.price == 200.0
    assert td.net_debt == 60.0          # 100 - 40
    assert td.day_change_pct == pytest.approx((200 - 195) / 195 * 100)

def test_tickerdata_from_info_defaults_missing_fields():
    td = TickerData.from_info("XYZ", {"currentPrice": 10.0}, None, None)
    assert td.name == "XYZ"             # longName отсутствует → symbol
    assert td.market_cap is None
    assert td.net_debt == 0.0           # нет долга/кэша → 0
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_data.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.data'`.

- [ ] **Step 3: Реализовать `core/data.py`**

```python
# core/data.py
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import streamlit as st
import yfinance as yf


# ─── safe + форматтеры ──────────────────────────────────────────────────────
def safe(info: dict, key: str, default: Any = None) -> Any:
    v = info.get(key, default)
    if v == "N/A" or v == "" or v is None:
        return default
    try:
        if isinstance(v, float) and np.isnan(v):
            return default
    except (TypeError, ValueError):
        pass
    return v


def _is_missing(n) -> bool:
    return n is None or (isinstance(n, float) and np.isnan(n))


def fmt_large(n) -> str:
    if _is_missing(n):
        return "N/A"
    if abs(n) >= 1e12:
        return f"${n / 1e12:.2f}T"
    if abs(n) >= 1e9:
        return f"${n / 1e9:.2f}B"
    if abs(n) >= 1e6:
        return f"${n / 1e6:.2f}M"
    return f"${n:,.0f}"


def fmt_pct(n) -> str:
    if _is_missing(n):
        return "N/A"
    return f"{n * 100:.1f}%"


def fmt_mult(n, suffix: str = "x") -> str:
    if _is_missing(n):
        return "N/A"
    return f"{n:.1f}{suffix}"


# ─── TickerData ─────────────────────────────────────────────────────────────
@dataclass
class TickerData:
    symbol: str
    name: str
    sector: str
    industry: str
    country: str
    website: str
    currency: str

    price: Optional[float]
    previous_close: Optional[float]
    market_cap: Optional[float]
    enterprise_value: Optional[float]
    week52_high: Optional[float]
    week52_low: Optional[float]

    trailing_pe: Optional[float]
    forward_pe: Optional[float]
    price_to_sales: Optional[float]
    price_to_book: Optional[float]
    ev_to_ebitda: Optional[float]
    ev_to_revenue: Optional[float]
    peg: Optional[float]
    dividend_yield: Optional[float]

    total_revenue: Optional[float]
    gross_profits: Optional[float]
    ebitda: Optional[float]
    net_income: Optional[float]
    free_cashflow: Optional[float]
    total_debt: Optional[float]
    total_cash: Optional[float]

    gross_margins: Optional[float]
    ebitda_margins: Optional[float]
    profit_margins: Optional[float]
    roe: Optional[float]
    roa: Optional[float]
    revenue_growth: Optional[float]

    description: str
    employees: Optional[int]
    shares_outstanding: Optional[float]
    beta: Optional[float]
    short_percent_float: Optional[float]

    history: Any = None       # pandas DataFrame или None
    financials: Any = None    # pandas DataFrame или None

    @property
    def net_debt(self) -> float:
        debt = self.total_debt or 0.0
        cash = self.total_cash or 0.0
        return debt - cash

    @property
    def day_change_pct(self) -> float:
        if self.price and self.previous_close:
            return (self.price - self.previous_close) / self.previous_close * 100
        return 0.0

    @classmethod
    def from_info(cls, symbol, info, history, financials) -> "TickerData":
        return cls(
            symbol=symbol,
            name=safe(info, "longName", symbol),
            sector=safe(info, "sector", "—"),
            industry=safe(info, "industry", "—"),
            country=safe(info, "country", "—"),
            website=safe(info, "website", ""),
            currency=safe(info, "currency", "USD"),
            price=safe(info, "currentPrice") or safe(info, "regularMarketPrice"),
            previous_close=safe(info, "previousClose"),
            market_cap=safe(info, "marketCap"),
            enterprise_value=safe(info, "enterpriseValue"),
            week52_high=safe(info, "fiftyTwoWeekHigh"),
            week52_low=safe(info, "fiftyTwoWeekLow"),
            trailing_pe=safe(info, "trailingPE"),
            forward_pe=safe(info, "forwardPE"),
            price_to_sales=safe(info, "priceToSalesTrailing12Months"),
            price_to_book=safe(info, "priceToBook"),
            ev_to_ebitda=safe(info, "enterpriseToEbitda"),
            ev_to_revenue=safe(info, "enterpriseToRevenue"),
            peg=safe(info, "pegRatio"),
            dividend_yield=safe(info, "dividendYield"),
            total_revenue=safe(info, "totalRevenue"),
            gross_profits=safe(info, "grossProfits"),
            ebitda=safe(info, "ebitda"),
            net_income=safe(info, "netIncomeToCommon"),
            free_cashflow=safe(info, "freeCashflow"),
            total_debt=safe(info, "totalDebt"),
            total_cash=safe(info, "totalCash"),
            gross_margins=safe(info, "grossMargins"),
            ebitda_margins=safe(info, "ebitdaMargins"),
            profit_margins=safe(info, "profitMargins"),
            roe=safe(info, "returnOnEquity"),
            roa=safe(info, "returnOnAssets"),
            revenue_growth=safe(info, "revenueGrowth"),
            description=safe(info, "longBusinessSummary", "Описание недоступно."),
            employees=safe(info, "fullTimeEmployees"),
            shares_outstanding=safe(info, "sharesOutstanding"),
            beta=safe(info, "beta"),
            short_percent_float=safe(info, "shortPercentOfFloat"),
            history=history,
            financials=financials,
        )

    def has_price(self) -> bool:
        return self.price is not None


# ─── Загрузка с кэшем ───────────────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def load_ticker(symbol: str) -> Optional[TickerData]:
    """Тянет данные из Yahoo и возвращает TickerData, либо None если тикер битый."""
    try:
        tk = yf.Ticker(symbol)
        info = tk.info
        if not info:
            return None
        history = tk.history(period="1y")
        try:
            financials = tk.financials
        except Exception:
            financials = None
        td = TickerData.from_info(symbol, info, history, financials)
        return td if td.has_price() else None
    except Exception:
        return None
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_data.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add core/data.py tests/test_data.py
git commit -m "feat: data layer — TickerData, safe, formatters, cached loader"
```

---

## Task 4: `core/compare.py` — сборка таблицы сравнения (TDD)

Строит структуру для вкладки Сравнение: строки-метрики, колонки-тикеры, плюс строка «Апсайд (Base DCF)». Также помечает лучшее/худшее значение в каждой строке для подсветки.

**Files:**
- Create: `core/compare.py`
- Test: `tests/test_compare.py`

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_compare.py
from core.data import TickerData
from core.compare import build_comparison_table, MetricRow

def _td(symbol, price, pe, roe):
    info = {"currentPrice": price, "trailingPE": pe, "returnOnEquity": roe,
            "longName": symbol}
    return TickerData.from_info(symbol, info, None, None)

def test_table_has_row_per_metric_and_column_per_ticker():
    tds = [_td("AAPL", 200, 30.0, 0.8), _td("MSFT", 400, 35.0, 0.4)]
    table = build_comparison_table(tds, base_upsides={"AAPL": 12.0, "MSFT": -5.0})
    assert [c for c in table.columns] == ["AAPL", "MSFT"]
    labels = [r.label for r in table.rows]
    assert "P/E" in labels
    assert "Апсайд (Base DCF)" in labels

def test_upside_row_uses_provided_values():
    tds = [_td("AAPL", 200, 30.0, 0.8), _td("MSFT", 400, 35.0, 0.4)]
    table = build_comparison_table(tds, base_upsides={"AAPL": 12.0, "MSFT": -5.0})
    upside_row = next(r for r in table.rows if r.label == "Апсайд (Base DCF)")
    assert upside_row.raw_values == [12.0, -5.0]

def test_best_worst_marked_lower_is_better_for_pe():
    tds = [_td("AAPL", 200, 30.0, 0.8), _td("MSFT", 400, 35.0, 0.4)]
    table = build_comparison_table(tds, base_upsides={"AAPL": 0.0, "MSFT": 0.0})
    pe_row = next(r for r in table.rows if r.label == "P/E")
    # ниже P/E лучше → AAPL (индекс 0) best, MSFT (индекс 1) worst
    assert pe_row.best_index == 0
    assert pe_row.worst_index == 1

def test_best_worst_marked_higher_is_better_for_roe():
    tds = [_td("AAPL", 200, 30.0, 0.8), _td("MSFT", 400, 35.0, 0.4)]
    table = build_comparison_table(tds, base_upsides={"AAPL": 0.0, "MSFT": 0.0})
    roe_row = next(r for r in table.rows if r.label == "ROE")
    assert roe_row.best_index == 0   # выше ROE лучше → AAPL
    assert roe_row.worst_index == 1

def test_missing_values_are_not_marked_best_worst():
    a = _td("AAPL", 200, 30.0, 0.8)
    b = _td("MSFT", 400, None, 0.4)   # нет P/E
    table = build_comparison_table([a, b], base_upsides={"AAPL": 0.0, "MSFT": 0.0})
    pe_row = next(r for r in table.rows if r.label == "P/E")
    assert pe_row.best_index == 0     # единственное валидное значение
    assert pe_row.worst_index == 0
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_compare.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.compare'`.

- [ ] **Step 3: Реализовать `core/compare.py`**

```python
# core/compare.py
from dataclasses import dataclass
from typing import Callable, Optional

from core.data import TickerData, fmt_large, fmt_mult, fmt_pct


@dataclass
class MetricRow:
    label: str
    raw_values: list           # сырые числа/None по тикерам
    display_values: list       # уже отформатированные строки
    best_index: Optional[int]  # индекс «лучшего» значения (для подсветки)
    worst_index: Optional[int]
    higher_is_better: bool


@dataclass
class ComparisonTable:
    columns: list              # тикеры
    rows: list                 # list[MetricRow]


# (label, extractor, formatter, higher_is_better)
_METRIC_SPECS: list = [
    ("Цена",           lambda t: t.price,           lambda v: fmt_large(v), True),
    ("Кап-я",          lambda t: t.market_cap,      lambda v: fmt_large(v), True),
    ("P/E",            lambda t: t.trailing_pe,     lambda v: fmt_mult(v),  False),
    ("Forward P/E",    lambda t: t.forward_pe,      lambda v: fmt_mult(v),  False),
    ("P/S",            lambda t: t.price_to_sales,  lambda v: fmt_mult(v),  False),
    ("EV/EBITDA",      lambda t: t.ev_to_ebitda,    lambda v: fmt_mult(v),  False),
    ("Gross Margin",   lambda t: t.gross_margins,   lambda v: fmt_pct(v),   True),
    ("Net Margin",     lambda t: t.profit_margins,  lambda v: fmt_pct(v),   True),
    ("ROE",            lambda t: t.roe,             lambda v: fmt_pct(v),   True),
    ("Рост выручки",   lambda t: t.revenue_growth,  lambda v: fmt_pct(v),   True),
    ("Div. Yield",     lambda t: t.dividend_yield,  lambda v: fmt_pct(v),   True),
]


def _mark_best_worst(values: list, higher_is_better: bool):
    valid = [(i, v) for i, v in enumerate(values) if v is not None]
    if not valid:
        return None, None
    best = (max if higher_is_better else min)(valid, key=lambda p: p[1])
    worst = (min if higher_is_better else max)(valid, key=lambda p: p[1])
    return best[0], worst[0]


def build_comparison_table(tickers: list, base_upsides: dict) -> ComparisonTable:
    """
    tickers: list[TickerData]
    base_upsides: {symbol: upside_pct_or_None} — апсайд Base-сценария DCF.
    """
    columns = [t.symbol for t in tickers]
    rows: list = []

    for label, extract, fmt, higher in _METRIC_SPECS:
        raw = [extract(t) for t in tickers]
        best, worst = _mark_best_worst(raw, higher)
        rows.append(MetricRow(
            label=label,
            raw_values=raw,
            display_values=[fmt(v) for v in raw],
            best_index=best,
            worst_index=worst,
            higher_is_better=higher,
        ))

    upside_raw = [base_upsides.get(t.symbol) for t in tickers]
    up_best, up_worst = _mark_best_worst(upside_raw, higher_is_better=True)
    rows.append(MetricRow(
        label="Апсайд (Base DCF)",
        raw_values=upside_raw,
        display_values=[f"{v:+.1f}%" if v is not None else "N/A" for v in upside_raw],
        best_index=up_best,
        worst_index=up_worst,
        higher_is_better=True,
    ))

    return ComparisonTable(columns=columns, rows=rows)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_compare.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add core/compare.py tests/test_compare.py
git commit -m "feat: comparison-table builder with best/worst marking"
```

---

## Task 5: `core/favorites.py` — избранное в localStorage (TDD чистых хелперов)

Чистые функции нормализации/добавления/удаления тестируем; тонкую обёртку над `streamlit-local-storage` — нет (проверим при запуске приложения).

**Files:**
- Create: `core/favorites.py`
- Test: `tests/test_favorites.py`

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_favorites.py
from core.favorites import normalize, add_symbol, remove_symbol

def test_normalize_uppercases_strips_dedups_preserves_order():
    assert normalize([" aapl ", "MSFT", "aapl", "", "nvda"]) == ["AAPL", "MSFT", "NVDA"]

def test_normalize_handles_none():
    assert normalize(None) == []

def test_add_symbol_appends_new():
    assert add_symbol(["AAPL"], "msft") == ["AAPL", "MSFT"]

def test_add_symbol_is_idempotent():
    assert add_symbol(["AAPL"], "aapl") == ["AAPL"]

def test_remove_symbol():
    assert remove_symbol(["AAPL", "MSFT"], "aapl") == ["MSFT"]

def test_remove_missing_is_noop():
    assert remove_symbol(["AAPL"], "TSLA") == ["AAPL"]
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_favorites.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.favorites'`.

- [ ] **Step 3: Реализовать `core/favorites.py`**

```python
# core/favorites.py
from streamlit_local_storage import LocalStorage

_STORAGE_KEY = "stock_analysator_favorites"


def normalize(symbols) -> list:
    """Upper-case, обрезать пробелы, выкинуть пустые, убрать дубли, сохранить порядок."""
    if not symbols:
        return []
    seen = set()
    out = []
    for s in symbols:
        if not s:
            continue
        sym = str(s).strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def add_symbol(symbols: list, symbol: str) -> list:
    return normalize(list(symbols) + [symbol])


def remove_symbol(symbols: list, symbol: str) -> list:
    target = str(symbol).strip().upper()
    return [s for s in normalize(symbols) if s != target]


# ─── Обёртка над браузерным localStorage ────────────────────────────────────
def _storage() -> LocalStorage:
    return LocalStorage()


def get_favorites() -> list:
    raw = _storage().getItem(_STORAGE_KEY)
    if not raw:
        return []
    return normalize([s for s in str(raw).split(",")])


def save_favorites(symbols: list) -> None:
    _storage().setItem(_STORAGE_KEY, ",".join(normalize(symbols)))


def add_favorite(symbol: str) -> list:
    updated = add_symbol(get_favorites(), symbol)
    save_favorites(updated)
    return updated


def remove_favorite(symbol: str) -> list:
    updated = remove_symbol(get_favorites(), symbol)
    save_favorites(updated)
    return updated
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_favorites.py -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add core/favorites.py tests/test_favorites.py
git commit -m "feat: favorites — pure list helpers + localStorage wrapper"
```

---

## Task 6: `ui/theme.py` и `ui/sidebar.py`

Переносим CSS из текущего `app.py` (строки 18–50) и слайдеры DCF (строки 144–161).

**Files:**
- Create: `ui/theme.py`, `ui/sidebar.py`

- [ ] **Step 1: Создать `ui/theme.py`**

```python
# ui/theme.py
import streamlit as st

_CSS = """
<style>
    .metric-card { background:#1e1e2e; border:1px solid #313244; border-radius:12px; padding:16px 20px; margin:4px 0; }
    .metric-label { color:#a6adc8; font-size:12px; text-transform:uppercase; letter-spacing:0.05em; }
    .metric-value { color:#cdd6f4; font-size:22px; font-weight:700; margin-top:4px; }
    .metric-sub { color:#6c7086; font-size:12px; margin-top:2px; }
    .scenario-bull { border-left:4px solid #a6e3a1; }
    .scenario-base { border-left:4px solid #89b4fa; }
    .scenario-bear { border-left:4px solid #f38ba8; }
    .upside-pos { color:#a6e3a1; font-weight:700; }
    .upside-neg { color:#f38ba8; font-weight:700; }
    .section-header { color:#cdd6f4; font-size:18px; font-weight:600; margin:24px 0 12px 0; padding-bottom:8px; border-bottom:1px solid #313244; }
    div[data-testid="stMetric"] { background:#1e1e2e; border:1px solid #313244; border-radius:12px; padding:12px 16px; }
    .cmp-best { color:#a6e3a1; font-weight:700; }
    .cmp-worst { color:#f38ba8; }
</style>
"""

def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
```

- [ ] **Step 2: Создать `ui/sidebar.py`**

```python
# ui/sidebar.py
from dataclasses import dataclass
import streamlit as st


@dataclass
class DcfParams:
    years: int
    wacc: float
    terminal_growth: float
    growth_rates: dict   # {"bear":..,"base":..,"bull":..}


def render_sidebar() -> DcfParams:
    with st.sidebar:
        st.markdown("## 📈 Stock Analysator")
        st.markdown("---")
        st.markdown("### ⚙️ DCF параметры")
        years = st.slider("Горизонт прогноза (лет)", 3, 10, 5)
        wacc = st.slider("WACC (%)", 5.0, 20.0, 10.0, 0.5) / 100
        terminal_growth = st.slider("Терминальный рост (%)", 1.0, 5.0, 2.5, 0.25) / 100

        st.markdown("#### Стартовый рост FCF (%/год)")
        st.caption("Рост в 1-й год. Дальше линейно затухает к терминальному.")
        bull_g = st.slider("🐂 Bull", 5, 40, 15) / 100
        base_g = st.slider("📊 Base", 0, 30, 8) / 100
        bear_g = st.slider("🐻 Bear", -10, 15, 2) / 100

        st.markdown("---")
        st.caption("Данные: Yahoo Finance (yfinance)")

    return DcfParams(
        years=years, wacc=wacc, terminal_growth=terminal_growth,
        growth_rates={"bear": bear_g, "base": base_g, "bull": bull_g},
    )
```

- [ ] **Step 3: Проверить импорт**

Run: `python -c "import ui.theme, ui.sidebar; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add ui/theme.py ui/sidebar.py
git commit -m "feat: extract theme CSS and DCF sidebar into ui/"
```

---

## Task 7: `ui/components.py` — переиспользуемые виджеты

Переносим отрисовку из текущего `app.py`: карточки сценариев, график цены, DCF-графики (waterfall + справедливая цена), график истории финансов. Работают от `TickerData` / `ScenarioResult`.

**Files:**
- Create: `ui/components.py`

- [ ] **Step 1: Создать `ui/components.py`**

```python
# ui/components.py
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from core.data import fmt_large

_PLOT_BG = "#181825"
_GRID = "#313244"
_AXIS = "#6c7086"

_SCENARIO_META = {
    "bear": ("🐻 Bear", "scenario-bear", "#f38ba8"),
    "base": ("📊 Base", "scenario-base", "#89b4fa"),
    "bull": ("🐂 Bull", "scenario-bull", "#a6e3a1"),
}


def section_header(text: str) -> None:
    st.markdown(f'<div class="section-header">{text}</div>', unsafe_allow_html=True)


def price_chart(history) -> None:
    if history is None or history.empty:
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=history.index, y=history["Close"], mode="lines",
        line=dict(color="#89b4fa", width=2),
        fill="tozeroy", fillcolor="rgba(137,180,250,0.08)", name="Цена",
    ))
    fig.update_layout(
        height=280, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(showgrid=False, color=_AXIS),
        yaxis=dict(showgrid=True, gridcolor=_GRID, color=_AXIS),
        plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def scenario_card(col, name: str, res, price: float) -> None:
    label, css_class, _ = _SCENARIO_META[name]
    iv = res.intrinsic
    upside = ((iv - price) / price * 100) if price else 0
    sign = "+" if upside >= 0 else ""
    upside_cls = "upside-pos" if upside >= 0 else "upside-neg"
    g_end = res.growth_path[-1] if res.growth_path else 0.0
    with col:
        st.markdown(f"""
        <div class="metric-card {css_class}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{f"${iv:.2f}" if iv > 0 else "N/A"}</div>
            <div class="metric-sub">
                Рост FCF: <b>{res.growth_start*100:.0f}% → {g_end*100:.1f}%</b><br>
                Апсайд: <span class="{upside_cls}">{sign}{upside:.1f}%</span><br>
                Доля терм. стоим.: <b>{res.tv_share*100:.0f}%</b>
            </div>
        </div>
        """, unsafe_allow_html=True)


def dcf_waterfall(base_res, years: int) -> None:
    labels = [f"Год {i+1}" for i in range(years)] + ["Терминальная стоимость"]
    vals = list(base_res.fcfs_pv) + [base_res.pv_terminal]
    fig = go.Figure(go.Bar(
        x=labels, y=vals,
        marker_color=["#89b4fa"] * years + ["#cba6f7"],
        text=[fmt_large(v) for v in vals], textposition="outside",
        textfont=dict(color="#cdd6f4", size=10),
    ))
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=False, color=_AXIS),
        yaxis=dict(showgrid=True, gridcolor=_GRID, color=_AXIS, tickformat="$.2s"),
        plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def dcf_fair_value(dcf_results: dict, price: float) -> None:
    order = ["bear", "base", "bull"]
    labels = [_SCENARIO_META[n][0] for n in order]
    intrinsics = [dcf_results[n].intrinsic for n in order]
    colors = [_SCENARIO_META[n][2] for n in order]
    fig = go.Figure(go.Bar(
        x=labels, y=intrinsics, marker_color=colors,
        text=[f"${iv:.2f}" for iv in intrinsics], textposition="outside",
    ))
    fig.add_hline(y=price, line_dash="dot", line_color="#f9e2af",
                  annotation_text=f"Текущая: ${price:.2f}",
                  annotation_font_color="#f9e2af")
    fig.update_layout(
        height=300, margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=False, color=_AXIS),
        yaxis=dict(showgrid=True, gridcolor=_GRID, color=_AXIS, tickprefix="$"),
        plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG, showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def financials_history(financials) -> None:
    try:
        if financials is None or financials.empty:
            st.caption("Историческая отчётность недоступна для этого тикера.")
            return
        rev_row = ni_row = None
        for key in ["Total Revenue", "Revenue"]:
            if key in financials.index:
                rev_row = financials.loc[key]
                break
        for key in ["Net Income", "Net Income Common Stockholders"]:
            if key in financials.index:
                ni_row = financials.loc[key]
                break
        if rev_row is None:
            st.caption("Историческая отчётность недоступна для этого тикера.")
            return
        cols = sorted(rev_row.index)
        rev_vals = [rev_row[c] for c in cols]
        ni_vals = [ni_row[c] if ni_row is not None else 0 for c in cols]
        years_fin = [str(c.year) for c in cols]

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=years_fin, y=rev_vals, name="Выручка",
                             marker_color="#89b4fa", opacity=0.8), secondary_y=False)
        fig.add_trace(go.Scatter(x=years_fin, y=ni_vals, name="Чистая прибыль",
                                 mode="lines+markers", line=dict(color="#a6e3a1", width=3),
                                 marker=dict(size=8)), secondary_y=True)
        fig.update_layout(
            height=320, margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(showgrid=False, color=_AXIS),
            yaxis=dict(showgrid=True, gridcolor=_GRID, color="#89b4fa", tickformat="$.2s", title="Выручка"),
            yaxis2=dict(color="#a6e3a1", tickformat="$.2s", title="Чистая прибыль"),
            plot_bgcolor=_PLOT_BG, paper_bgcolor=_PLOT_BG,
            legend=dict(bgcolor="#1e1e2e", bordercolor=_GRID),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.caption("Историческая отчётность недоступна для этого тикера.")
```

- [ ] **Step 2: Проверить импорт**

Run: `python -c "import ui.components; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add ui/components.py
git commit -m "feat: reusable UI components (cards, price/dcf/financials charts)"
```

---

## Task 8: `app.py` (вход) + вкладка Анализ

Превращаем старый `app.py` в тонкий вход (конфиг + сайдбар + приветствие), а весь текущий экран переносим в `pages/1_📊_Анализ.py`, собирая его из `core` и `ui`.

**Files:**
- Modify: `app.py` (полностью переписать)
- Create: `pages/1_📊_Анализ.py`

- [ ] **Step 1: Переписать `app.py`**

```python
# app.py
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
```

- [ ] **Step 2: Создать `pages/1_📊_Анализ.py`**

```python
# pages/1_📊_Анализ.py
import streamlit as st

from core.data import (load_ticker, fmt_large, fmt_pct, fmt_mult)
from core.dcf import run_dcf
from core.favorites import add_favorite
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
if not td.free_cashflow or not td.shares_outstanding:
    st.warning("Недостаточно данных для DCF (нет FCF или кол-ва акций).")
else:
    dcf = run_dcf(
        fcf_base=td.free_cashflow, growth_rates=params.growth_rates,
        wacc=params.wacc, terminal_growth=params.terminal_growth,
        years=params.years, shares=td.shares_outstanding, net_debt=td.net_debt,
    )
    cols = st.columns(3)
    for col, name in zip(cols, ["bear", "base", "bull"]):
        C.scenario_card(col, name, dcf[name], td.price)

    st.caption(f"WACC: {params.wacc*100:.1f}% · Терминальный рост: "
               f"{params.terminal_growth*100:.1f}% · Горизонт: {params.years} лет · "
               f"Чистый долг: {fmt_large(td.net_debt)}")

    max_tv = max(r.tv_share for r in dcf.values())
    if max_tv > 0.75:
        st.warning(f"⚠️ Терминальная стоимость даёт до {max_tv*100:.0f}% оценки — "
                   "результат сильно зависит от WACC и терминального роста. "
                   "Увеличь горизонт или снизь стартовый рост.")

    st.markdown("##### Структура стоимости (Base сценарий)")
    C.dcf_waterfall(dcf["base"], params.years)
    st.markdown("##### Справедливая цена vs текущая")
    C.dcf_fair_value(dcf, td.price)

C.section_header("📅 История финансов")
C.financials_history(td.financials)

st.markdown("---")
st.caption("⚠️ Только для образовательных целей. Не является инвестиционной рекомендацией.")
```

- [ ] **Step 3: Запустить приложение и проверить вкладку Анализ**

Run: `streamlit run app.py`
Проверить в браузере (`localhost:8501`):
- Открывается главная с описанием и меню слева.
- Вкладка «Анализ»: `AAPL` грузится, видны метрики, график, DCF-карточки, waterfall, «справедливая цена», история финансов.
- Кнопка «⭐ В избранное» показывает toast.
- Ввести битый тикер (`ZZZZ`) → аккуратная ошибка.

Expected: всё отображается как в старом `app.py`, без трейсбеков.

- [ ] **Step 4: Прогнать тесты (регрессия)**

Run: `pytest -q`
Expected: PASS (все тесты из Task 2–5).

- [ ] **Step 5: Commit**

```bash
git add app.py "pages/1_📊_Анализ.py"
git commit -m "feat: multipage entry + Analysis page assembled from core/ui"
```

---

## Task 9: `pages/2_⚖️_Сравнение.py` — вкладка Сравнение

**Files:**
- Create: `pages/2_⚖️_Сравнение.py`

- [ ] **Step 1: Создать страницу**

```python
# pages/2_⚖️_Сравнение.py
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
        (tickers if td is not None else missing).append(td if td is not None else sym)

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
```

- [ ] **Step 2: Запустить и проверить**

Run: `streamlit run app.py`
В браузере открыть «Сравнение»:
- По умолчанию `AAPL, MSFT, NVDA` (или из избранного) грузятся в таблицу.
- Строки — метрики, столбцы — тикеры; есть строка «Апсайд (Base DCF)».
- В каждой строке подсвечено лучшее (зелёным) и худшее (красным).
- Битый тикер в списке → предупреждение «Не найдены: …», остальные показаны.

Expected: таблица корректна, без трейсбеков.

- [ ] **Step 3: Commit**

```bash
git add "pages/2_⚖️_Сравнение.py"
git commit -m "feat: Comparison page — metrics table with Base-DCF upside"
```

---

## Task 10: `pages/3_⭐_Избранное.py` — вкладка Избранное

**Files:**
- Create: `pages/3_⭐_Избранное.py`

- [ ] **Step 1: Создать страницу**

```python
# pages/3_⭐_Избранное.py
import streamlit as st

from core.data import load_ticker, fmt_large
from core.dcf import run_dcf
from core.favorites import get_favorites, add_favorite, remove_favorite
from ui.theme import inject_theme
from ui.sidebar import render_sidebar

st.set_page_config(page_title="Избранное · Stock Analysator", page_icon="⭐", layout="wide")
inject_theme()
params = render_sidebar()

st.markdown("# ⭐ Избранное")
st.caption("Тикеры хранятся в твоём браузере (localStorage). У каждого посетителя — свои.")

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
        if td.free_cashflow and td.shares_outstanding and td.price:
            dcf = run_dcf(fcf_base=td.free_cashflow, growth_rates=params.growth_rates,
                          wacc=params.wacc, terminal_growth=params.terminal_growth,
                          years=params.years, shares=td.shares_outstanding, net_debt=td.net_debt)
            iv = dcf["base"].intrinsic
            up = (iv - td.price) / td.price * 100 if iv > 0 else None
            c_up.metric("Апсайд Base", f"{up:+.1f}%" if up is not None else "N/A")
        else:
            c_up.metric("Апсайд Base", "N/A")
    if c_del.button("🗑", key=f"del_{sym}"):
        remove_favorite(sym)
        st.rerun()

st.markdown("---")
st.caption("⚠️ Только для образовательных целей. Не является инвестиционной рекомендацией.")
```

- [ ] **Step 2: Запустить и проверить сквозной сценарий избранного**

Run: `streamlit run app.py`
Проверить:
- На «Анализ» нажать «⭐ В избранное» для `AAPL`, затем открыть «Избранное» → `AAPL` в списке с ценой, изменением, апсайдом.
- Добавить `TSLA` вручную → появляется.
- Нажать 🗑 у тикера → исчезает (после rerun).
- **Перезагрузить страницу браузера (F5)** → список сохранился (проверка localStorage).

Expected: избранное персистентно между перезагрузками.

- [ ] **Step 3: Commit**

```bash
git add "pages/3_⭐_Избранное.py"
git commit -m "feat: Favorites page backed by localStorage"
```

---

## Task 11: README + подготовка к деплою

**Files:**
- Create: `README.md`
- Modify: `CLAUDE.md` (обновить раздел структуры)

- [ ] **Step 1: Создать `README.md`**

```markdown
# 📈 Stock Analysator

Веб-приложение для анализа акций US-рынка: тикер → метрики, мультипликаторы,
финансы и **DCF-оценка по трём сценариям** (Bear / Base / Bull).

**Вкладки:** 📊 Анализ · ⚖️ Сравнение · ⭐ Избранное (хранится в браузере).

## Запуск локально

```bash
pip install -r requirements.txt
streamlit run app.py
```

Откроется на http://localhost:8501

## Тесты

```bash
pytest
```

## Деплой (Streamlit Community Cloud)

1. Запушить репозиторий на GitHub.
2. Зайти на https://share.streamlit.io, подключить репозиторий, указать `app.py`.
3. Получить публичный URL. Каждый `git push` обновляет приложение.

## Стек

Python · Streamlit (multipage) · yfinance · plotly · pandas · numpy

## Дисклеймер

Только для образовательных целей. Не является инвестиционной рекомендацией.
```

- [ ] **Step 2: Обновить раздел структуры в `CLAUDE.md`**

Заменить в `CLAUDE.md` раздел «## Стек и запуск» упоминание «Один файл: `app.py`» на описание модульной структуры (`core/`, `ui/`, `pages/`) и добавить, что тесты в `tests/`, запуск `pytest`.

- [ ] **Step 3: Финальная проверка — тесты + приложение**

Run: `pytest -q && streamlit run app.py`
Expected: все тесты PASS; приложение запускается, все три вкладки работают.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: README and updated project structure notes"
```

---

## Задел на будущее (НЕ реализуем сейчас — YAGNI)

- Второй источник данных (Financial Modeling Prep) как фолбэк к yfinance.
- Слайдер скорости затухания роста (сейчас всегда линейное).
- Реверс-DCF: «какой рост заложен в текущую цену».
- Экспорт сравнения в Excel.
- Полноценное портфолио (позиции, количество, P/L) поверх Избранного.
```
