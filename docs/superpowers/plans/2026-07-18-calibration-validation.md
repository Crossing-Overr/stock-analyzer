# Calibration + Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** WACC из CAPM по бете (по умолчанию, с ручным режимом), горизонт по умолчанию 10 лет, и скрипт валидации всех цифр/логики/актуальности — с фиксами найденного.

**Architecture:** Новый чистый модуль `core/wacc.py` (CAPM + клампы + учёт долга); `core/data.py` получает кэшированную живую ставку 10-леток (^TNX) и хелпер выбора базы FCF; сайдбар — галочку авто-WACC; все три страницы считают действующий WACC per-ticker. `validate.py` — standalone-скрипт перекрёстной проверки: наши цифры против сырого yfinance и здравого смысла.

**Tech Stack:** Python 3.9, Streamlit, yfinance, pytest.

**Спека:** `docs/superpowers/specs/2026-07-18-calibration-validation-design.md`

**Важно про окружение:** на этом Mac `pip`/`streamlit`/`pytest` НЕ в PATH — только `python3 -m`. Python 3.9 → `Optional[...]`, НЕ `X | None`. В `st.caption`/`st.info` парные `$` рендерятся как LaTeX — текст с `fmt_large(...)` экранировать `.replace("$", "\\$")` (в сырых HTML-блоках не нужно).

---

## Файловая структура

```
core/
├── wacc.py            # НОВЫЙ: estimate_wacc (CAPM+долг+клампы), effective_wacc
├── data.py            # +tnx_to_rate, +load_risk_free (кэш 1ч), +TickerData.dcf_fcf_base
ui/
├── sidebar.py         # галочка авто-WACC, условный ползунок, горизонт 3–15 деф.10
pages/
├── 1_📊_Анализ.py      # effective_wacc, разбор CAPM, свежесть данных в футере
├── 2_⚖️_Сравнение.py   # per-ticker effective_wacc + SBC-консистентная база
└── 3_⭐_Избранное.py    # то же
validate.py            # НОВЫЙ: 4 группы проверок, ✅/⚠️/❌, exit 1 при ❌
tests/
├── test_wacc.py       # НОВЫЙ
└── test_data.py       # +tnx_to_rate, +dcf_fcf_base
```

**Границы:** `core/wacc.py` ни от чего в проекте не зависит (rf передаётся аргументом — нет циклических импортов). `validate.py` сознательно смотрит и в наш пайплайн, и в сырой yfinance — перекрёстная проверка.

---

## Task 1: `core/wacc.py` — CAPM с клампами и долгом (TDD)

**Files:**
- Create: `core/wacc.py`
- Test: `tests/test_wacc.py`

- [ ] **Step 1: Написать падающие тесты**

```python
# tests/test_wacc.py
import math
from core.wacc import (estimate_wacc, effective_wacc, WaccEstimate,
                       ERP, RF_DEFAULT, BETA_MIN, BETA_MAX, WACC_MIN, WACC_MAX)

RF = 0.045


def test_capm_formula_no_debt():
    # beta=1, без долга: WACC = Re = rf + 1.0*ERP = 0.045 + 0.05 = 0.095
    est = estimate_wacc(beta=1.0, risk_free=RF, market_cap=100e9, total_debt=0)
    assert isinstance(est, WaccEstimate)
    assert math.isclose(est.cost_of_equity, 0.095, abs_tol=1e-9)
    assert math.isclose(est.wacc, 0.095, abs_tol=1e-9)
    assert est.beta_used == 1.0
    assert est.debt_weight == 0.0


def test_low_beta_clamped_up():
    # KO-кейс: beta 0.35 — артефакт; клампится к BETA_MIN=0.5
    est = estimate_wacc(beta=0.35, risk_free=RF, market_cap=100e9, total_debt=0)
    assert est.beta_raw == 0.35
    assert est.beta_used == BETA_MIN
    assert math.isclose(est.cost_of_equity, RF + BETA_MIN * ERP, abs_tol=1e-9)


def test_high_beta_clamped_down():
    est = estimate_wacc(beta=3.0, risk_free=RF, market_cap=100e9, total_debt=0)
    assert est.beta_used == BETA_MAX


def test_wacc_floor():
    # Низкая rf + низкая бета → сырой WACC ниже пола → клампится к WACC_MIN
    est = estimate_wacc(beta=0.5, risk_free=0.02, market_cap=100e9, total_debt=0)
    assert math.isclose(est.wacc, WACC_MIN, abs_tol=1e-9)


def test_wacc_ceiling():
    est = estimate_wacc(beta=2.5, risk_free=0.06, market_cap=100e9, total_debt=0)
    assert math.isclose(est.wacc, WACC_MAX, abs_tol=1e-9)


def test_debt_lowers_wacc_below_cost_of_equity():
    # E=80, D=20: Rd=rf+0.01 < Re, плюс налоговый щит → WACC < Re
    est = estimate_wacc(beta=1.0, risk_free=RF, market_cap=80e9, total_debt=20e9)
    assert est.wacc < est.cost_of_equity
    assert math.isclose(est.debt_weight, 0.2, abs_tol=1e-9)
    # ручной расчёт: Re=0.095, Rd=0.055, Rd_after_tax=0.055*0.79=0.04345
    expected = (80 * 0.095 + 20 * 0.04345) / 100
    assert math.isclose(est.wacc, expected, abs_tol=1e-9)


def test_none_when_no_beta_or_cap():
    assert estimate_wacc(beta=None, risk_free=RF, market_cap=100e9, total_debt=0) is None
    assert estimate_wacc(beta=1.0, risk_free=RF, market_cap=None, total_debt=0) is None
    assert estimate_wacc(beta=1.0, risk_free=RF, market_cap=0, total_debt=0) is None


def test_missing_debt_treated_as_zero():
    est = estimate_wacc(beta=1.0, risk_free=RF, market_cap=100e9, total_debt=None)
    assert math.isclose(est.wacc, est.cost_of_equity, abs_tol=1e-9)


def test_missing_rf_uses_default():
    est = estimate_wacc(beta=1.0, risk_free=None, market_cap=100e9, total_debt=0)
    assert math.isclose(est.risk_free, RF_DEFAULT, abs_tol=1e-9)


def test_effective_wacc_auto_and_fallbacks():
    # auto + есть данные → CAPM; auto + нет беты → ручное; manual → ручное
    w = effective_wacc(beta=1.0, risk_free=RF, market_cap=100e9, total_debt=0,
                       auto=True, manual=0.10)
    assert math.isclose(w, 0.095, abs_tol=1e-9)
    assert effective_wacc(beta=None, risk_free=RF, market_cap=100e9, total_debt=0,
                          auto=True, manual=0.10) == 0.10
    assert effective_wacc(beta=1.0, risk_free=RF, market_cap=100e9, total_debt=0,
                          auto=False, manual=0.11) == 0.11
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python3 -m pytest tests/test_wacc.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.wacc'`

- [ ] **Step 3: Реализовать `core/wacc.py`**

```python
# core/wacc.py
from dataclasses import dataclass
from typing import Optional

# Параметры CAPM. ERP — премия рынка акций США к безрисковой ставке.
ERP = 0.05
RF_DEFAULT = 0.045          # фолбэк, если ^TNX недоступен
BETA_MIN, BETA_MAX = 0.5, 2.5   # экстремальные беты — статистические артефакты
WACC_MIN, WACC_MAX = 0.065, 0.16
DEBT_SPREAD = 0.01          # стоимость долга ≈ rf + спред
TAX_RATE = 0.21             # корп. налог США (налоговый щит долга)


@dataclass
class WaccEstimate:
    wacc: float
    cost_of_equity: float
    risk_free: float
    beta_raw: float
    beta_used: float        # после клампа
    debt_weight: float      # D / (D + E)


def estimate_wacc(beta, risk_free, market_cap, total_debt) -> Optional[WaccEstimate]:
    """
    WACC по CAPM с упрощённым учётом долга.

    Re = rf + beta*ERP; Rd = rf + спред; WACC = (E*Re + D*Rd*(1-tax)) / (E+D).
    Бета клампится в [BETA_MIN, BETA_MAX], итог — в [WACC_MIN, WACC_MAX].
    None, если нет беты или капитализации (UI откатится на ползунок).
    """
    if beta is None or not market_cap or market_cap <= 0:
        return None
    rf = risk_free if risk_free is not None else RF_DEFAULT

    beta_used = min(max(float(beta), BETA_MIN), BETA_MAX)
    cost_of_equity = rf + beta_used * ERP

    debt = float(total_debt) if total_debt else 0.0
    total = market_cap + debt
    debt_weight = debt / total if total > 0 else 0.0

    cost_of_debt_after_tax = (rf + DEBT_SPREAD) * (1 - TAX_RATE)
    raw = (market_cap * cost_of_equity + debt * cost_of_debt_after_tax) / total
    wacc = min(max(raw, WACC_MIN), WACC_MAX)

    return WaccEstimate(
        wacc=wacc,
        cost_of_equity=cost_of_equity,
        risk_free=rf,
        beta_raw=float(beta),
        beta_used=beta_used,
        debt_weight=debt_weight,
    )


def effective_wacc(beta, risk_free, market_cap, total_debt, auto: bool, manual: float) -> float:
    """Действующий WACC: CAPM в авто-режиме (если данных хватает), иначе ползунок."""
    if auto:
        est = estimate_wacc(beta, risk_free, market_cap, total_debt)
        if est is not None:
            return est.wacc
    return manual
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `python3 -m pytest tests/test_wacc.py -q`
Expected: PASS (10 passed)

- [ ] **Step 5: Полная сюита**

Run: `python3 -m pytest -q`
Expected: `69 passed` (59 старых + 10 новых)

- [ ] **Step 6: Commit**

```bash
git add core/wacc.py tests/test_wacc.py
git commit -m "feat: CAPM-based WACC with beta/WACC clamps and debt adjustment"
```

---

## Task 2: `core/data.py` — живая ставка ^TNX + выбор базы FCF (TDD)

**Files:**
- Modify: `core/data.py`
- Test: `tests/test_data.py`

- [ ] **Step 1: Дописать падающие тесты в конец `tests/test_data.py`**

Дополнить импорт вверху файла: к строке `from core.data import ...` добавить `tnx_to_rate`.

```python
def test_tnx_to_rate_converts_percent_to_fraction():
    # ^TNX котируется в процентах: 4.541 → 0.04541
    assert tnx_to_rate(4.541) == pytest.approx(0.04541)


def test_tnx_to_rate_rejects_garbage():
    assert tnx_to_rate(None) is None
    assert tnx_to_rate(0.5) is None     # 0.005 — ниже санитарного минимума 1%
    assert tnx_to_rate(45.0) is None    # 0.45 — выше санитарного максимума 10%


def test_dcf_fcf_base_selection():
    cf = _cashflow({"Free Cash Flow": [30.0, 20.0, 10.0],
                    "Stock Based Compensation": [3.0, 2.0, 1.0]})
    td = TickerData.from_info("X", {"currentPrice": 5.0}, None, None, cf)
    assert td.dcf_fcf_base(subtract_sbc=True) == 18.0    # ex-SBC доступен
    assert td.dcf_fcf_base(subtract_sbc=False) == 20.0   # галочка выключена

    cf2 = _cashflow({"Free Cash Flow": [30.0, 20.0, 10.0]})
    td2 = TickerData.from_info("X", {"currentPrice": 5.0}, None, None, cf2)
    assert td2.dcf_fcf_base(subtract_sbc=True) == 20.0   # SBC нет → обычная база
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python3 -m pytest tests/test_data.py -q`
Expected: FAIL — `ImportError: cannot import name 'tnx_to_rate'`

- [ ] **Step 3: Реализовать в `core/data.py`**

Добавить после `subtract_series`:

```python
# Санитарные границы для доходности 10-леток (^TNX котируется в процентах)
_RF_SANE_MIN, _RF_SANE_MAX = 0.01, 0.10


def tnx_to_rate(price) -> Optional[float]:
    """^TNX (4.541 = 4.541%) → дробь 0.04541. Мусор/вне диапазона → None."""
    if price is None:
        return None
    try:
        rate = float(price) / 100.0
    except (TypeError, ValueError):
        return None
    if not (_RF_SANE_MIN <= rate <= _RF_SANE_MAX):
        return None
    return rate
```

Добавить в конец файла (после `load_ticker`):

```python
@st.cache_data(ttl=3600, show_spinner=False)
def load_risk_free():
    """
    Живая доходность 10-летних гособлигаций США из ^TNX.
    Возвращает (ставка, live): live=False → сработал фолбэк RF_DEFAULT.
    """
    from core.wacc import RF_DEFAULT
    try:
        info = yf.Ticker("^TNX").info
        rate = tnx_to_rate(safe(info, "regularMarketPrice")
                           or safe(info, "previousClose"))
        if rate is not None:
            return rate, True
    except Exception:
        pass
    return RF_DEFAULT, False
```

Добавить метод в класс `TickerData` (после свойства `day_change_pct`):

```python
    def dcf_fcf_base(self, subtract_sbc: bool) -> Optional[float]:
        """База FCF для DCF: ex-SBC, если попросили и данные есть, иначе обычная."""
        if subtract_sbc and self.fcf_normalized_ex_sbc is not None:
            return self.fcf_normalized_ex_sbc
        return self.fcf_normalized
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `python3 -m pytest tests/test_data.py -q`
Expected: PASS (все старые + 3 новых)

- [ ] **Step 5: Проверить живой ^TNX**

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -c "
import warnings; warnings.filterwarnings('ignore')
from core.data import load_risk_free
print(load_risk_free())
" 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn|No runtime"
```
Expected: примерно `(0.045, True)` — дробь в диапазоне 0.03–0.06 и `True`.

- [ ] **Step 6: Полная сюита + commit**

Run: `python3 -m pytest -q`
Expected: `72 passed`

```bash
git add core/data.py tests/test_data.py
git commit -m "feat: live 10Y treasury rate (^TNX, cached) + dcf_fcf_base helper"
```

---

## Task 3: `ui/sidebar.py` — галочка авто-WACC + горизонт 10 лет

**Files:**
- Modify: `ui/sidebar.py`

- [ ] **Step 1: Полностью заменить содержимое `ui/sidebar.py`**

Изменения против текущего: `DcfParams.wacc_auto`, ползунок WACC рендерится только в ручном режиме, горизонт 3–15 с дефолтом 10.

```python
from dataclasses import dataclass
import streamlit as st


@dataclass
class DcfParams:
    years: int
    wacc: float          # значение ползунка — используется в ручном режиме
    wacc_auto: bool      # True → страницы считают WACC по CAPM (бета тикера)
    terminal_growth: float
    growth_rates: dict   # {"bear":..,"base":..,"bull":..}
    subtract_sbc: bool


def render_sidebar() -> DcfParams:
    with st.sidebar:
        st.markdown("## 📈 Stock Analysator")
        st.markdown("---")
        st.markdown("### ⚙️ DCF параметры")
        # key= обязателен: иначе значения сбрасываются при смене вкладки
        years = st.slider("Горизонт прогноза (лет)", 3, 15, 10, key="dcf_years")

        wacc_auto = st.checkbox(
            "WACC автоматически (CAPM)", value=True, key="dcf_wacc_auto",
            help="Ставка из беты тикера: rf(10-летки) + β × 5%, с учётом долга. "
                 "У каждой компании — своя. Сними галочку, чтобы задать вручную.",
        )
        if wacc_auto:
            st.caption("WACC считается по бете тикера — см. подпись под DCF.")
            wacc = st.session_state.get("dcf_wacc", 10.0) / 100
        else:
            wacc = st.slider("WACC (%)", 5.0, 20.0, 10.0, 0.5, key="dcf_wacc") / 100

        terminal_growth = st.slider("Терминальный рост (%)", 1.0, 5.0, 2.5, 0.25,
                                    key="dcf_tg") / 100

        st.markdown("#### Стартовый рост FCF (%/год)")
        st.caption("Рост в 1-й год. Дальше линейно затухает к терминальному.")
        bull_g = st.slider("🐂 Bull", 5, 40, 15, key="dcf_bull") / 100
        base_g = st.slider("📊 Base", 0, 30, 8, key="dcf_base") / 100
        bear_g = st.slider("🐻 Bear", -10, 15, 2, key="dcf_bear") / 100

        st.markdown("---")
        subtract_sbc = st.checkbox(
            "Вычитать SBC из FCF", value=True, key="dcf_sbc",
            help="Компенсация акциями — реальные расходы: она размывает твою долю. "
                 "Yahoo её из FCF не вычитает, поэтому оценка получается завышенной.",
        )

        st.markdown("---")
        st.caption("Данные: Yahoo Finance (yfinance)")

    return DcfParams(
        years=years, wacc=wacc, wacc_auto=wacc_auto,
        terminal_growth=terminal_growth,
        growth_rates={"bear": bear_g, "base": base_g, "bull": bull_g},
        subtract_sbc=subtract_sbc,
    )
```

- [ ] **Step 2: Импорт-проверка + сюита**

Run: `python3 -c "import ui.sidebar; print('ok')" 2>&1 | grep -v Warning && python3 -m pytest -q 2>&1 | tail -1`
Expected: `ok`, `72 passed`

- [ ] **Step 3: Commit**

```bash
git add ui/sidebar.py
git commit -m "feat: auto-WACC checkbox (CAPM) and 10y default horizon (range 3-15)"
```

---

## Task 4: Вкладка «Анализ» — effective WACC, разбор CAPM, свежесть

**Files:**
- Modify: `pages/1_📊_Анализ.py`

READ THE FILE FIRST. Точки правок:

- [ ] **Step 1: Импорты**

К `from core.data import (load_ticker, fmt_large, fmt_pct, fmt_mult)` добавить `load_risk_free`. После строки импорта `core.dcf_analysis` добавить:

```python
from core.wacc import estimate_wacc, ERP
```

- [ ] **Step 2: Вычислить действующий WACC**

Сразу ПОСЛЕ блока выбора базы FCF (строки `use_sbc = ...` / `fcf_base = ...`) вставить:

```python
# ─── Действующий WACC: CAPM по бете (auto) или ползунок ─────────────────────
rf, rf_live = load_risk_free()
wacc_est = (estimate_wacc(td.beta, rf, td.market_cap, td.total_debt)
            if params.wacc_auto else None)
eff_wacc = wacc_est.wacc if wacc_est is not None else params.wacc
```

- [ ] **Step 3: Заменить все использования `params.wacc` на `eff_wacc`**

В файле ровно 4 места (кроме сайдбара, который не трогаем):
1. `run_dcf(... wacc=params.wacc ...)` → `wacc=eff_wacc`
2. caption `WACC: {params.wacc*100:.1f}%` → `WACC: {eff_wacc*100:.1f}%`
3. `implied_growth(... wacc=params.wacc ...)` → `wacc=eff_wacc`
4. `sensitivity_grid(... wacc=params.wacc ...)` → `wacc=eff_wacc`

Проверить: `grep -n "params.wacc" "pages/1_📊_Анализ.py"` после правки должен показать только `params.wacc_auto` (и ничего с голым `params.wacc`).

- [ ] **Step 4: Разбор CAPM под подписью базы FCF**

Сразу после существующего `st.caption((f"{base_note} · WACC: ...").replace("$", "\\$"))` добавить:

```python
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
```

- [ ] **Step 5: Свежесть данных в футере**

Заменить финальные строки

```python
st.markdown("---")
st.caption("⚠️ Только для образовательных целей. Не является инвестиционной рекомендацией.")
```

на

```python
st.markdown("---")
if td.history is not None and not td.history.empty:
    _ts = td.history.index[-1]
    st.caption(f"Данные: Yahoo Finance · цена на {_ts.strftime('%d.%m.%Y %H:%M')}")
st.caption("⚠️ Только для образовательных целей. Не является инвестиционной рекомендацией.")
```

- [ ] **Step 6: Компиляция + сюита + AppTest**

Run: `python3 -m py_compile "pages/1_📊_Анализ.py" && python3 -m pytest -q 2>&1 | tail -1`
Expected: компилируется, `72 passed`

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -c "
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('pages/1_📊_Анализ.py', default_timeout=90)
at.run()
print('exception:', bool(at.exception))
caps = [c.value for c in at.caption]
print('CAPM-разбор:', any('CAPM' in c for c in caps))
print('свежесть:', any('цена на' in c for c in caps))
for c in caps:
    if 'CAPM' in c or 'цена на' in c: print('  ', c[:110])
# ручной режим: снять галочку
at2 = AppTest.from_file('pages/1_📊_Анализ.py', default_timeout=90)
at2.run()
at2.checkbox(key='dcf_wacc_auto').set_value(False).run()
caps2 = [c.value for c in at2.caption]
print('manual mode exception:', bool(at2.exception))
print('в ручном режиме CAPM-разбора нет:', not any('= CAPM' in c for c in caps2))
" 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn|No runtime|ScriptRunContext"
```
Expected: `exception: False`, CAPM-разбор True, свежесть True; в ручном режиме разбора нет, исключений нет.

- [ ] **Step 7: Commit**

```bash
git add "pages/1_📊_Анализ.py"
git commit -m "feat: effective CAPM WACC on Analysis page + freshness footer"
```

---

## Task 5: Сравнение и Избранное — per-ticker WACC + SBC-консистентность

Сейчас обе страницы игнорируют галочку SBC (используют `td.fcf_normalized` напрямую) — это несогласованность с Анализом. Чиним заодно через `td.dcf_fcf_base(...)`.

**Files:**
- Modify: `pages/2_⚖️_Сравнение.py`, `pages/3_⭐_Избранное.py`

READ BOTH FILES FIRST.

- [ ] **Step 1: `pages/2_⚖️_Сравнение.py`**

К импортам из `core.data` добавить `load_risk_free`; добавить строку `from core.wacc import effective_wacc`.

Найти блок:

```python
# апсайд Base-сценария для каждого (по нормализованному FCF; None если непригодно)
base_upsides = {
    td.symbol: dcf_upside_base(
        td.fcf_normalized, td.price, td.shares_outstanding, td.net_debt,
        params.growth_rates, params.wacc, params.terminal_growth, params.years,
    )
    for td in tickers
}
```

Заменить на:

```python
# апсайд Base-сценария: SBC-консистентная база + per-ticker CAPM-WACC
rf, _rf_live = load_risk_free()
base_upsides = {}
for td in tickers:
    w = effective_wacc(td.beta, rf, td.market_cap, td.total_debt,
                       auto=params.wacc_auto, manual=params.wacc)
    base_upsides[td.symbol] = dcf_upside_base(
        td.dcf_fcf_base(params.subtract_sbc), td.price, td.shares_outstanding,
        td.net_debt, params.growth_rates, w, params.terminal_growth, params.years,
    )
```

Найти caption под таблицей (`f"Апсайд считается по Base-сценарию DCF при текущих слайдерах (WACC {params.wacc*100:.1f}%, ..."`) и заменить формулировку WACC:

```python
wacc_txt = "CAPM по бете каждого тикера" if params.wacc_auto else f"{params.wacc*100:.1f}%"
st.caption(f"Апсайд считается по Base-сценарию DCF при текущих слайдерах "
           f"(WACC: {wacc_txt}, горизонт {params.years} лет). "
           "Зелёным — лучшее в строке, красным — худшее.")
```

- [ ] **Step 2: `pages/3_⭐_Избранное.py`**

Те же импорты (`load_risk_free`, `from core.wacc import effective_wacc`). После `params = render_sidebar()` добавить `rf, _rf_live = load_risk_free()`.

Найти вызов:

```python
        up = dcf_upside_base(
            td.fcf_normalized, td.price, td.shares_outstanding, td.net_debt,
            params.growth_rates, params.wacc, params.terminal_growth, params.years,
        )
```

Заменить на:

```python
        w = effective_wacc(td.beta, rf, td.market_cap, td.total_debt,
                           auto=params.wacc_auto, manual=params.wacc)
        up = dcf_upside_base(
            td.dcf_fcf_base(params.subtract_sbc), td.price, td.shares_outstanding,
            td.net_debt, params.growth_rates, w, params.terminal_growth, params.years,
        )
```

- [ ] **Step 3: Компиляция + AppTest smoke**

Run: `python3 -m py_compile "pages/2_⚖️_Сравнение.py" "pages/3_⭐_Избранное.py" && echo ok`
Expected: `ok`

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -c "
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
for page in ['pages/2_⚖️_Сравнение.py', 'pages/3_⭐_Избранное.py']:
    at = AppTest.from_file(page, default_timeout=120)
    at.run()
    print(page.split('/')[-1], 'exception:', bool(at.exception))
    if at.exception: print(at.exception)
" 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn|No runtime|ScriptRunContext"
```
Expected: обе страницы `exception: False`.

- [ ] **Step 4: Commit**

```bash
git add "pages/2_⚖️_Сравнение.py" "pages/3_⭐_Избранное.py"
git commit -m "feat: per-ticker CAPM WACC + SBC-consistent FCF base on Compare/Favorites"
```

---

## Task 6: `validate.py` — скрипт валидации

**Files:**
- Create: `validate.py`

- [ ] **Step 1: Создать `validate.py`**

```python
#!/usr/bin/env python3
"""
Валидация цифр, логики модели, адекватности и актуальности.

Запуск:  python3 validate.py            # дефолтная корзина
         python3 validate.py AAPL KO    # свои тикеры

Каждая проверка печатает ✅/⚠️/❌ с цифрами. Выход с кодом 1, если есть ❌.
"""
import datetime
import math
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
               "SBC уменьшает базу", f"{fmt_large(td.fcf_normalized_ex_sbc)} < {fmt_large(td.fcf_normalized)}")

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
        report("⚠️" if not strict else "❌", f"Заложенный рост ({wacc_txt})", "вне диапазона −50..100%")
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
```

- [ ] **Step 2: Запустить**

Run: `cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 validate.py 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn|No runtime"`

Expected: полный отчёт по 9 тикерам + битому. **Вставить вывод в отчёт полностью.** Ожидаемо возможны ❌/⚠️ — это и есть цель валидации.

- [ ] **Step 3: Commit (сам скрипт, до фиксов)**

```bash
git add validate.py
git commit -m "feat: validate.py — cross-checks data, model logic, adequacy, freshness"
```

- [ ] **Step 4: НЕ чинить найденное самостоятельно**

Каждый ❌ доложить контроллеру списком: проверка, тикер, цифры. Контроллер решает, что чинить (возможны отдельные диспатчи) — пороги адекватности могут требовать обсуждения с владельцем, это не механический фикс.

---

## Task 7: Финализация — CLAUDE.md, полная проверка

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Обновить `CLAUDE.md`**

Раздел «### ⚠️ Известная проблема калибровки (не решена)» заменить на:

```markdown
### Калибровка (решена 2026-07-18)

WACC по умолчанию считается из CAPM по бете тикера (`core/wacc.py`):
`rf(^TNX, кэш 1ч) + β×5%` с учётом долга; бета клампится [0.5–2.5], WACC —
[6.5%–16%]. Горизонт по умолчанию 10 лет (ползунок 3–15). Галочка «WACC
автоматически» в сайдбаре; снял — работает ручной ползунок. Валидация:
`python3 validate.py` (данные, логика, адекватность, актуальность).
```

В «Возможные следующие шаги» убрать строку про калибровку.

- [ ] **Step 2: Полная проверка**

Run: `python3 -m pytest -q 2>&1 | tail -1`
Expected: `72 passed`

Run: перезапустить приложение и открыть `http://localhost:8501/Анализ` — AAPL: разбор CAPM в подписи, WACC ≈ 9–10%, заложенный рост ЗАМЕТНО ниже 77%; снять галочку авто → ползунок вернулся.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: calibration resolved — CAPM WACC, 10y horizon, validate.py"
```

- [ ] **Step 4: НЕ пушить**

**СТОП:** `git push` = автодеплой публичного приложения. Только с явного разрешения владельца.
