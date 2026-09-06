# Terminal Multiple Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать альтернативу формуле Гордона — терминальную стоимость как «FCF последнего года × мультипликатор» (подход Свена Карлина), с пробросом по всей цепочке расчётов.

**Architecture:** `run_dcf` получает необязательный `terminal_multiple`; когда он задан, терминал считается по мультипликатору вместо Гордона. Параметр протаскивается через `dcf_analysis` (реверс-DCF, сетка) и `dcf_upside_base`, чтобы все числа на странице были согласованы. Сайдбар получает переключатель режима; `DcfParams` — поле `terminal_multiple`.

**Tech Stack:** Python 3.9, Streamlit, pytest.

**Спека:** `docs/superpowers/specs/2026-09-06-terminal-multiple-design.md`

**Окружение:** `pip`/`streamlit`/`pytest` НЕ в PATH — только `python3 -m`. Python 3.9 → `Optional[...]`, НЕ `X | None`.

**Правило про `$`:** в `st.caption`/`st.info` парные `$` рендерятся как LaTeX (уже ловили). В сырых HTML-блоках `$` безопасен.

---

## Файловая структура

```
core/
├── dcf.py           # +terminal_multiple в run_dcf и dcf_upside_base
├── dcf_analysis.py  # проброс через _intrinsic, implied_*, sensitivity_grid
ui/
├── sidebar.py       # переключатель режима терминала, DcfParams.terminal_multiple
pages/
├── 1_📊_Анализ.py    # проброс + сетка в режиме мультипликатора
├── 2,3              # проброс в ticker_base_upside (через params — уже есть)
└── 4_💎_Идеи.py      # подпись, что снимок считан по Гордону
tests/
├── test_dcf.py           # +терминал по мультипликатору
└── test_dcf_analysis.py  # +round-trip и сетка в новом режиме
```

**Ключевой принцип:** параметр везде необязательный (`None` = Гордон), поэтому существующие вызовы и 91 тест не ломаются.

---

## Task 1: `core/dcf.py` — терминал по мультипликатору (TDD)

**Files:**
- Modify: `core/dcf.py`
- Test: `tests/test_dcf.py`

- [ ] **Step 1: Дописать падающие тесты в конец `tests/test_dcf.py`**

```python
def test_terminal_multiple_replaces_gordon():
    """Терминал = FCF последнего года × мультипликатор, ровно."""
    # fcf 100, рост 0 (старт = терминальный), 1 год → FCF_1 = 100
    res = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                  terminal_growth=0.0, years=1, shares=10.0, net_debt=0.0,
                  terminal_multiple=15.0)
    r = res["base"]
    # TV = 100 * 15 = 1500; приведённая = 1500/1.1 = 1363.636...
    assert math.isclose(r.pv_terminal, 1500.0 / 1.1, rel_tol=1e-12)
    # EV = PV(FCF года 1) + PV(TV) = 100/1.1 + 1500/1.1 = 1600/1.1
    assert math.isclose(r.enterprise_value, 1600.0 / 1.1, rel_tol=1e-12)
    assert math.isclose(r.intrinsic, (1600.0 / 1.1) / 10.0, rel_tol=1e-12)


def test_terminal_multiple_ignores_terminal_growth():
    """В режиме мультипликатора терминальный рост на терминал не влияет."""
    a = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                terminal_growth=0.0, years=5, shares=10.0, net_debt=0.0,
                terminal_multiple=15.0)["base"]
    b = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                terminal_growth=0.04, years=5, shares=10.0, net_debt=0.0,
                terminal_multiple=15.0)["base"]
    # терминал одинаков; отличаются только траектории роста (затухание к разным g)
    assert math.isclose(a.pv_terminal / a.fcfs_pv[-1],
                        b.pv_terminal / b.fcfs_pv[-1], rel_tol=1e-9)


def test_none_multiple_is_gordon_unchanged():
    """None → поведение ровно как раньше (золотой тест не меняется)."""
    with_none = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                        terminal_growth=0.0, years=1, shares=10.0, net_debt=0.0,
                        terminal_multiple=None)["base"]
    default = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                      terminal_growth=0.0, years=1, shares=10.0, net_debt=0.0)["base"]
    assert math.isclose(with_none.intrinsic, 100.0, rel_tol=1e-9)   # прежний golden
    assert math.isclose(with_none.intrinsic, default.intrinsic, rel_tol=1e-12)


def test_non_positive_multiple_falls_back_to_gordon():
    """Мультипликатор ≤ 0 трактуется как «не задан» — иначе терминал отрицательный."""
    fallback = run_dcf(fcf_base=100.0, growth_rates={"base": 0.0}, wacc=0.10,
                       terminal_growth=0.0, years=1, shares=10.0, net_debt=0.0,
                       terminal_multiple=0.0)["base"]
    assert math.isclose(fallback.intrinsic, 100.0, rel_tol=1e-9)


def test_dcf_upside_base_accepts_terminal_multiple():
    """Апсайд в режиме мультипликатора выше, чем по Гордону при тех же входных."""
    common = dict(fcf_base=100.0, price=50.0, shares=10.0, net_debt=0.0,
                  growth_rates={"bear": 0.0, "base": 0.0, "bull": 0.0},
                  wacc=0.10, terminal_growth=0.025, years=10)
    gordon = dcf_upside_base(**common)
    mult = dcf_upside_base(**common, terminal_multiple=25.0)
    assert gordon is not None and mult is not None
    assert mult > gordon        # 25x щедрее, чем Гордон при 10%/2.5% (≈13.7x)
```

Также добавить `dcf_upside_base` в импорт вверху файла — заменить строку
`from core.dcf import run_dcf, ScenarioResult` на
`from core.dcf import run_dcf, ScenarioResult, dcf_upside_base`.

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python3 -m pytest tests/test_dcf.py -q`
Expected: FAIL — `TypeError: run_dcf() got an unexpected keyword argument 'terminal_multiple'`

- [ ] **Step 3: Реализовать в `core/dcf.py`**

Изменить сигнатуру `run_dcf`:
```python
def run_dcf(fcf_base, growth_rates, wacc, terminal_growth, years, shares, net_debt,
            terminal_multiple=None):
```

Дополнить докстринг после строки про 2-фазную модель:
```python
    terminal_multiple: если задан (>0) — терминальная стоимость считается как
        FCF последнего года × мультипликатор (подход Карлина), а не по формуле
        Гордона. Полезно, потому что Гордон при WACC 10%/росте 2.5% эквивалентен
        всего ≈13.5x FCF, тогда как качественные компании торгуются много дороже.
```

Заменить блок расчёта терминальной стоимости:
```python
        terminal_fcf = fcf * (1 + eff_terminal)
        terminal_value = terminal_fcf / (wacc - eff_terminal)
        pv_terminal = terminal_value / (1 + wacc) ** years
```
на:
```python
        if terminal_multiple and terminal_multiple > 0:
            # Терминал по мультипликатору: «во сколько FCF оценят компанию в конце»
            terminal_value = fcf * terminal_multiple
        else:
            terminal_fcf = fcf * (1 + eff_terminal)
            terminal_value = terminal_fcf / (wacc - eff_terminal)
        pv_terminal = terminal_value / (1 + wacc) ** years
```

Изменить сигнатуру `dcf_upside_base` и проброс:
```python
def dcf_upside_base(fcf_base, price, shares, net_debt,
                    growth_rates, wacc, terminal_growth, years,
                    terminal_multiple=None):
```
и внутри — в вызове `run_dcf(...)` добавить `terminal_multiple=terminal_multiple`.

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `python3 -m pytest tests/test_dcf.py -q`
Expected: PASS (11 passed — 6 прежних + 5 новых)

- [ ] **Step 5: Полная сюита**

Run: `python3 -m pytest -q`
Expected: `96 passed` (91 + 5)

- [ ] **Step 6: Commit**

```bash
git add core/dcf.py tests/test_dcf.py
git commit -m "feat(dcf): optional terminal multiple instead of Gordon growth"
```

---

## Task 2: `core/dcf_analysis.py` — проброс в реверс-DCF и сетку (TDD)

**Files:**
- Modify: `core/dcf_analysis.py`
- Test: `tests/test_dcf_analysis.py`

- [ ] **Step 1: Дописать падающие тесты в конец `tests/test_dcf_analysis.py`**

```python
def test_implied_growth_roundtrip_with_terminal_multiple():
    """Round-trip работает и в режиме мультипликатора."""
    from core.dcf import run_dcf as _run
    fair = _run(fcf_base=100.0, growth_rates={"base": 0.08}, wacc=0.10,
                terminal_growth=0.025, years=10, shares=10.0, net_debt=0.0,
                terminal_multiple=20.0)["base"].intrinsic
    g = implied_growth(price=fair, fcf_base=100.0, shares=10.0, net_debt=0.0,
                       wacc=0.10, terminal_growth=0.025, years=10,
                       terminal_multiple=20.0)
    assert g is not None and math.isclose(g, 0.08, abs_tol=1e-4)


def test_implied_growth_multiple_gives_lower_implied_than_gordon():
    """При щедром терминале та же цена оправдывается меньшим ростом."""
    common = dict(price=200.0, fcf_base=100.0, shares=10.0, net_debt=0.0,
                  wacc=0.10, terminal_growth=0.025, years=10)
    g_gordon = implied_growth(**common)
    g_mult = implied_growth(**common, terminal_multiple=25.0)
    assert g_gordon is not None and g_mult is not None
    assert g_mult < g_gordon


def test_implied_return_accepts_terminal_multiple():
    r = implied_return(price=150.0, fcf_base=100.0, shares=10.0, net_debt=0.0,
                       growth_start=0.08, terminal_growth=0.025, years=10,
                       terminal_multiple=20.0)
    assert r is not None and 0.0 < r < 0.5


def test_sensitivity_grid_varies_multiple_when_given():
    """В режиме мультипликатора вторая ось — мультипликатор, пустых ячеек нет."""
    g = sensitivity_grid(fcf_base=100.0, price=50.0, shares=10.0, net_debt=0.0,
                         growth_start=0.08, wacc=0.10, terminal_growth=0.025,
                         years=10, terminal_multiple=15.0)
    assert g.multiples is not None                    # ось мультипликаторов
    assert g.terminal_growths is None                 # ось терм. роста не используется
    assert len(g.multiples) == 5 and len(g.cells) == 5
    assert math.isclose(g.multiples[2], 15.0, abs_tol=1e-9)      # центр
    assert math.isclose(g.multiples[0], 11.0, abs_tol=1e-9)      # ±2 шага по 2x
    assert math.isclose(g.multiples[4], 19.0, abs_tol=1e-9)
    assert all(c.intrinsic is not None for row in g.cells for c in row)
    assert sum(1 for row in g.cells for c in row if c.is_current) == 1


def test_sensitivity_grid_gordon_mode_unchanged():
    """Без мультипликатора сетка прежняя: ось терм. роста, multiples=None."""
    g = sensitivity_grid(fcf_base=100.0, price=50.0, shares=10.0, net_debt=0.0,
                         growth_start=0.08, wacc=0.10, terminal_growth=0.025,
                         years=10)
    assert g.multiples is None
    assert g.terminal_growths is not None and len(g.terminal_growths) == 5
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python3 -m pytest tests/test_dcf_analysis.py -q`
Expected: FAIL — `TypeError: implied_growth() got an unexpected keyword argument 'terminal_multiple'`

- [ ] **Step 3: Реализовать в `core/dcf_analysis.py`**

`_intrinsic` — добавить параметр и проброс:
```python
def _intrinsic(fcf_base, growth_start, wacc, terminal_growth, years, shares, net_debt,
               terminal_multiple=None) -> float:
    """Справедливая цена одного сценария. Тонкая обёртка над моделью."""
    res = run_dcf(
        fcf_base=fcf_base,
        growth_rates={"base": growth_start},
        wacc=wacc,
        terminal_growth=terminal_growth,
        years=years,
        shares=shares,
        net_debt=net_debt,
        terminal_multiple=terminal_multiple,
    )
    return res["base"].intrinsic
```

`implied_growth` — добавить параметр в сигнатуру (перед `lo`/`hi`) и в замыкание:
```python
def implied_growth(price, fcf_base, shares, net_debt, wacc, terminal_growth, years,
                   terminal_multiple=None,
                   lo: float = GROWTH_LO, hi: float = GROWTH_HI) -> Optional[float]:
```
и внутри:
```python
    def f(g):
        return _intrinsic(fcf_base, g, wacc, terminal_growth, years, shares, net_debt,
                          terminal_multiple) - price
```

`implied_return` — аналогично:
```python
def implied_return(price, fcf_base, shares, net_debt, growth_start, terminal_growth, years,
                   terminal_multiple=None, hi: float = RETURN_HI) -> Optional[float]:
```
и внутри:
```python
    def f(r):
        return _intrinsic(fcf_base, growth_start, r, terminal_growth, years, shares,
                          net_debt, terminal_multiple) - price
```

`ticker_base_upside` — проброс из params:
```python
    return dcf_upside_base(
        td.dcf_fcf_base(params.subtract_sbc), td.price, td.shares_outstanding,
        td.net_debt, params.growth_rates, wacc, params.terminal_growth, params.years,
        terminal_multiple=getattr(params, "terminal_multiple", None),
    )
```

Константа шага мультипликатора рядом с `TG_STEP`:
```python
MULT_STEP = 2.0      # шаг оси мультипликатора в сетке чувствительности
```

`SensitivityGrid` — вторая ось становится опциональной:
```python
@dataclass
class SensitivityGrid:
    waccs: list                          # значения по столбцам
    terminal_growths: Optional[list]     # ось строк в режиме Гордона (иначе None)
    multiples: Optional[list]            # ось строк в режиме мультипликатора (иначе None)
    cells: list                          # list[list[SensitivityCell]]
```

`SensitivityCell` — добавить поле мультипликатора:
```python
@dataclass
class SensitivityCell:
    wacc: float
    terminal_growth: Optional[float]   # None в режиме мультипликатора
    multiple: Optional[float]          # None в режиме Гордона
    intrinsic: Optional[float]
    upside: Optional[float]
    is_current: bool
```

`sensitivity_grid` — полностью заменить на версию с двумя режимами:
```python
def sensitivity_grid(fcf_base, price, shares, net_debt, growth_start,
                     wacc, terminal_growth, years, terminal_multiple=None,
                     wacc_step: float = WACC_STEP, tg_step: float = TG_STEP,
                     mult_step: float = MULT_STEP,
                     radius: int = GRID_RADIUS) -> Optional[SensitivityGrid]:
    """
    Сетка чувствительности вокруг текущих настроек. Рост FCF берётся базовый и не
    варьируется. Ось строк зависит от режима терминала: терминальный рост (Гордон)
    или мультипликатор. None, если DCF в принципе неприменим.
    """
    if not _inputs_valid(price, fcf_base, shares):
        return None

    waccs = [wacc + i * wacc_step for i in range(-radius, radius + 1)]
    use_mult = bool(terminal_multiple and terminal_multiple > 0)

    if use_mult:
        row_vals = [terminal_multiple + i * mult_step for i in range(-radius, radius + 1)]
    else:
        row_vals = [terminal_growth + i * tg_step for i in range(-radius, radius + 1)]

    rows = []
    for rv in row_vals:
        row = []
        for w in waccs:
            centre = (abs(rv - (terminal_multiple if use_mult else terminal_growth)) < 1e-9)
            is_current = (abs(w - wacc) < 1e-9) and centre
            if use_mult:
                iv = _intrinsic(fcf_base, growth_start, w, terminal_growth, years,
                                shares, net_debt, rv)
                upside = (iv - price) / price * 100 if iv > 0 else None
                row.append(SensitivityCell(w, None, rv, iv, upside, is_current))
                continue
            if rv >= w:      # ограничение Гордона: терм. рост должен быть ниже WACC
                row.append(SensitivityCell(w, rv, None, None, None, is_current))
                continue
            iv = _intrinsic(fcf_base, growth_start, w, rv, years, shares, net_debt)
            upside = (iv - price) / price * 100 if iv > 0 else None
            row.append(SensitivityCell(w, rv, None, iv, upside, is_current))
        rows.append(row)

    return SensitivityGrid(waccs=waccs,
                           terminal_growths=None if use_mult else row_vals,
                           multiples=row_vals if use_mult else None,
                           cells=rows)
```

- [ ] **Step 4: Починить существующие тесты сетки**

Существующие тесты в `tests/test_dcf_analysis.py` обращаются к
`c.terminal_growth` и создают `SensitivityCell` неявно — проверить их и, если
падают из-за нового поля `multiple`, поправить обращения. Конкретно тест
`test_cells_where_terminal_ge_wacc_are_empty` использует `c.terminal_growth >= c.wacc`
— он остаётся валидным в режиме Гордона.

Run: `python3 -m pytest tests/test_dcf_analysis.py -q`
Expected: PASS (все прежние + 5 новых)

- [ ] **Step 5: Обновить рендер сетки под новую структуру**

В `ui/components.py`, функция `sensitivity_table` — подпись строки берётся из
`row[0].terminal_growth`, что в режиме мультипликатора будет `None`. Заменить
формирование `label` и заголовок:

```python
    is_mult = grid.multiples is not None
    corner = "Мультипл. ↓ / WACC →" if is_mult else "Терм. рост ↓ / WACC →"
```
и в цикле строк заменить
```python
        label = f"{row[0].terminal_growth * 100:.2f}%"
```
на
```python
        label = (f"{row[0].multiple:.0f}x" if is_mult
                 else f"{row[0].terminal_growth * 100:.2f}%")
```
и в разметке таблицы заменить текст заголовка первой колонки
`Терм. рост ↓ / WACC →` на `{corner}`.

- [ ] **Step 6: Полная сюита + commit**

Run: `python3 -m pytest -q`
Expected: `101 passed` (96 + 5)

```bash
git add core/dcf_analysis.py ui/components.py tests/test_dcf_analysis.py
git commit -m "feat(dcf): propagate terminal multiple through reverse-DCF and sensitivity grid"
```

---

## Task 3: `ui/sidebar.py` — переключатель режима терминала

**Files:**
- Modify: `ui/sidebar.py`

- [ ] **Step 1: Добавить поле в `DcfParams`**

```python
@dataclass
class DcfParams:
    years: int
    wacc: float          # значение ползунка — используется в ручном режиме
    wacc_auto: bool      # True → страницы считают WACC по CAPM (бета тикера)
    terminal_growth: float
    terminal_multiple: Optional[float]   # None → терминал по Гордону
    growth_rates: dict   # {"bear":..,"base":..,"bull":..}
    subtract_sbc: bool
```
и добавить импорт вверху файла: `from typing import Optional`.

- [ ] **Step 2: Заменить блок терминального роста на переключатель**

Найти строку:
```python
        terminal_growth = st.slider("Терминальный рост (%)", 1.0, 5.0, 2.5, 0.25,
                                    key="dcf_tg") / 100
```
и заменить на:
```python
        term_mode = st.radio(
            "Терминальная стоимость", ["Рост (Гордон)", "Мультипликатор"],
            key="dcf_term_mode",
            help="Гордон: вечная рента при заданном росте. Мультипликатор (подход "
                 "Карлина): «во сколько FCF оценят компанию в конце горизонта» — "
                 "нынешний Гордон при WACC 10% эквивалентен всего ≈13.5x.",
        )
        terminal_growth = st.slider("Терминальный рост (%)", 1.0, 5.0, 2.5, 0.25,
                                    key="dcf_tg") / 100
        if term_mode == "Мультипликатор":
            terminal_multiple = float(st.slider(
                "Мультипликатор к FCF последнего года", 5, 40, 15, 1, key="dcf_mult"))
            st.caption("Терминальный рост в этом режиме не влияет на терминал, "
                       "но задаёт, к чему затухает рост FCF.")
        else:
            terminal_multiple = None
```

- [ ] **Step 3: Вернуть новое поле**

В `return DcfParams(...)` добавить `terminal_multiple=terminal_multiple,`:
```python
    return DcfParams(
        years=years, wacc=wacc, wacc_auto=wacc_auto,
        terminal_growth=terminal_growth, terminal_multiple=terminal_multiple,
        growth_rates={"bear": bear_g, "base": base_g, "bull": bull_g},
        subtract_sbc=subtract_sbc,
    )
```

- [ ] **Step 4: Проверить**

Run: `cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -c "import ui.sidebar; print('ok')" 2>&1 | grep -v Warning && python3 -m pytest -q 2>&1 | tail -1`
Expected: `ok`, `101 passed`

- [ ] **Step 5: Commit**

```bash
git add ui/sidebar.py
git commit -m "feat(ui): terminal-value mode switch (Gordon growth / multiple)"
```

---

## Task 4: Проброс на страницах

**Files:**
- Modify: `pages/1_📊_Анализ.py`, `pages/4_💎_Идеи.py`

READ BOTH FILES FIRST. Страницы 2 и 3 менять НЕ нужно — они используют
`ticker_base_upside(td, params, rf)`, который уже забирает `terminal_multiple`
из `params` (сделано в Task 2).

- [ ] **Step 1: `pages/1_📊_Анализ.py` — проброс в четыре вызова**

Добавить `terminal_multiple=params.terminal_multiple,` в:

1. `run_dcf(...)` — вызов, где считается `dcf`
2. `implied_growth(...)`
3. `implied_return(...)`
4. `sensitivity_grid(...)`

- [ ] **Step 2: Показать режим в подписи условий**

Найти строку формирования подписи:
```python
    st.caption((f"{base_note}{wacc_note} · горизонт {params.years} лет · "
                f"терм. рост {params.terminal_growth*100:.1f}%").replace("$", "\\$"))
```
и заменить на:
```python
    term_note = (f"терминал {params.terminal_multiple:.0f}x FCF"
                 if params.terminal_multiple
                 else f"терм. рост {params.terminal_growth*100:.1f}%")
    st.caption((f"{base_note}{wacc_note} · горизонт {params.years} лет · "
                f"{term_note}").replace("$", "\\$"))
```

- [ ] **Step 3: `pages/4_💎_Идеи.py` — честная подпись про Гордон**

Найти строку статуса:
```python
fresh = "· 🔄 цены обновлены сейчас" if live else ""
```
и сразу после блока `st.caption(f"Фундамент на {res.as_of} ...")` добавить:
```python
if params_terminal_multiple_active():
    st.caption("⚠️ Подборка посчитана по терминальному росту (Гордон) — снимок "
               "предпосчитан. Режим мультипликатора действует на вкладке «Анализ».")
```

Поскольку страница «Идеи» не вызывает `render_sidebar()`, взять режим из
`st.session_state` — добавить вспомогательную проверку прямо в файле, выше места
использования:
```python
def params_terminal_multiple_active() -> bool:
    """Включён ли на других вкладках режим терминального мультипликатора."""
    return st.session_state.get("dcf_term_mode") == "Мультипликатор"
```

- [ ] **Step 4: Проверка — компиляция, сюита, AppTest**

Run: `cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -m py_compile pages/*.py && echo "compile ok" && python3 -m pytest -q 2>&1 | tail -1`
Expected: `compile ok`, `101 passed`

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -c "
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
for p in ['pages/1_📊_Анализ.py','pages/2_⚖️_Сравнение.py','pages/3_⭐_Избранное.py','pages/4_💎_Идеи.py']:
    at = AppTest.from_file(p, default_timeout=120); at.run()
    print(f\"  {p.split('/')[-1]:28} exception: {bool(at.exception)}\")
    if at.exception: print('   ', at.exception)
" 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn|No runtime|ScriptRunContext"
```
Expected: все четыре `exception: False`. PASTE OUTPUT.

- [ ] **Step 5: Проверить оба режима на «Анализе»**

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -c "
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('pages/1_📊_Анализ.py', default_timeout=90)
at.run()
caps = [c.value for c in at.caption]
print('Гордон:', [c for c in caps if 'терм. рост' in c][:1])
at.radio(key='dcf_term_mode').set_value('Мультипликатор').run()
caps2 = [c.value for c in at.caption]
print('Мультипликатор:', [c for c in caps2 if 'терминал' in c][:1])
print('exception:', bool(at.exception))
" 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn|No runtime|ScriptRunContext"
```
Expected: в режиме Гордона подпись содержит «терм. рост», после переключения — «терминал 15x FCF», без исключений. PASTE OUTPUT.

- [ ] **Step 6: Commit**

```bash
git add pages/
git commit -m "feat(ui): wire terminal multiple through Analysis; note Gordon-only Ideas snapshot"
```

---

## Task 5: Проверка эффекта и доки (выполняет контроллер)

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Померить эффект на живых данных**

Прогнать AAPL/KO/GOOGL в обоих режимах и сравнить справедливые цены и вердикты —
понять, снимает ли мультипликатор вопрос о консерватизме.

- [ ] **Step 2: Обновить `CLAUDE.md`**

В раздел про DCF-модель добавить:

```markdown
### Терминальная стоимость: два режима

- **Гордон** (по умолчанию): `FCF×(1+g)/(WACC−g)`. При WACC 10% и росте 2.5%
  эквивалентен всего ≈13.5x FCF — отсюда системный консерватизм.
- **Мультипликатор** (подход Свена Карлина): `FCF последнего года × мультипликатор`,
  дефолт 15x. Переключатель в сайдбаре; параметр `terminal_multiple` пробрасывается
  через реверс-DCF и сетку чувствительности (в этом режиме ось сетки —
  WACC × мультипликатор).
- Вкладка «Идеи» всегда считает по Гордону: снимок предпосчитан.
```

- [ ] **Step 3: Финальная проверка и commit**

Run: `python3 -m pytest -q 2>&1 | tail -1`
Expected: `101 passed`

```bash
git add CLAUDE.md
git commit -m "docs: document terminal-value modes"
```

- [ ] **Step 4: НЕ пушить без разрешения владельца**

**СТОП:** `git push` = автодеплой публичного приложения. Только с явного «пуш».

---

## Задел на будущее (НЕ сейчас — YAGNI)

- Полная модель Карлина: две фазы роста (1–5 и 6–10), фиксированная ставка,
  три сценария с вероятностями — отдельный блок рядом с нашим DCF.
- Пересборка снимка «Идей» с выбором режима терминала.
