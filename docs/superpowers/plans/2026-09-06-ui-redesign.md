# UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Причесать интерфейс в «тёмный финтех»: вердикт сверху, иерархия вместо стены плиток, единая палитра в токенах.

**Architecture:** `ui/theme.py` становится единственным источником цветов (`COLORS` + генерация CSS). `ui/components.py` берёт цвета оттуда и получает новые компоненты (вердикт, шкала сценариев, строки метрик, хедер). `pages/1` пересобирается по новому порядку; остальные страницы точечно перекрашиваются. Расчётная логика `core/` не трогается.

**Tech Stack:** Python 3.9, Streamlit, plotly, pytest.

**Спека:** `docs/superpowers/specs/2026-09-06-ui-redesign-design.md`

**Окружение:** `pip`/`streamlit`/`pytest` НЕ в PATH — только `python3 -m`. Python 3.9 → `Optional[...]`, НЕ `X | None`.

**Ключевое правило про `$`:** в `st.caption`/`st.markdown` обычным текстом парные `$` рендерятся как LaTeX (уже ловили этот баг). В сырых HTML-блоках через `unsafe_allow_html=True` — `$` безопасен. Все новые карточки — сырой HTML, экранировать там НЕ надо.

---

## Файловая структура

```
ui/
├── theme.py         # COLORS (токены) + CSS из них + inject_theme()  ← источник правды
├── components.py    # берёт цвета из theme; +verdict_card, +scenario_scale,
│                    #   +metric_rows, +ticker_header
├── sidebar.py       # без изменений
pages/
├── 1_📊_Анализ.py    # пересборка порядка: вердикт → реверс → график → метрики → блоки
├── 2,3,4            # точечная замена захардкоженных цветов на токены
.streamlit/
└── config.toml      # тема Streamlit в тон новой палитре
tests/
└── test_theme.py    # НОВЫЙ: verdict_for() пороги
```

**Границы:** `ui/theme.py` ничего не импортирует из проекта. `ui/components.py` импортирует `theme` и `core.data` (только форматтеры). Страницы — сборка.

---

## Task 1: `ui/theme.py` — токены палитры + `verdict_for` (TDD)

**Files:**
- Modify: `ui/theme.py`
- Create: `tests/test_theme.py`

- [ ] **Step 1: Написать падающие тесты — `tests/test_theme.py`**

```python
from ui.theme import COLORS, verdict_for


def test_palette_has_required_tokens():
    for key in ("bg", "surface", "elevated", "border", "text", "text_dim",
                "text_muted", "accent", "accent2", "pos", "neg", "warn"):
        assert key in COLORS
        assert COLORS[key].startswith("#")


def test_verdict_undervalued_above_15pct():
    label, color_key = verdict_for(30.0)
    assert label == "НЕДООЦЕНЕНА"
    assert color_key == "pos"


def test_verdict_fair_within_band():
    assert verdict_for(0.0)[0] == "СПРАВЕДЛИВО"
    assert verdict_for(14.9)[0] == "СПРАВЕДЛИВО"
    assert verdict_for(-14.9)[0] == "СПРАВЕДЛИВО"


def test_verdict_overvalued_below_minus15pct():
    label, color_key = verdict_for(-68.5)
    assert label == "ПЕРЕОЦЕНЕНА"
    assert color_key == "neg"


def test_verdict_boundaries_are_inclusive_outside_band():
    assert verdict_for(15.0)[0] == "НЕДООЦЕНЕНА"
    assert verdict_for(-15.0)[0] == "ПЕРЕОЦЕНЕНА"


def test_verdict_none_when_upside_unknown():
    assert verdict_for(None) is None
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `python3 -m pytest tests/test_theme.py -q`
Expected: FAIL — `ImportError: cannot import name 'COLORS' from 'ui.theme'`

- [ ] **Step 3: Полностью заменить `ui/theme.py`**

```python
from typing import Optional, Tuple

import streamlit as st

# ─── Токены палитры — единственный источник цветов в приложении ──────────────
COLORS = {
    "bg":         "#0f1116",   # фон страницы
    "surface":    "#16181f",   # карточки
    "elevated":   "#1c1f28",   # вложенные элементы, полосы
    "border":     "#242833",   # границы
    "text":       "#f4f4f5",   # основной текст
    "text_dim":   "#a1a1aa",   # вторичный
    "text_muted": "#71717a",   # подписи
    "accent":     "#6366f1",   # индиго
    "accent2":    "#8b5cf6",   # фиолетовый (градиент)
    "pos":        "#22c55e",   # рост / недооценена
    "neg":        "#ef4444",   # падение / переоценена
    "warn":       "#f59e0b",   # риск
}

# Сценарии DCF: (подпись, ключ цвета)
SCENARIO_META = {
    "bear": ("Bear", "neg"),
    "base": ("Base", "accent"),
    "bull": ("Bull", "pos"),
}

# Порог, за которым считаем бумагу недо-/переоценённой (в процентах апсайда)
VERDICT_BAND = 15.0


def verdict_for(upside) -> Optional[Tuple[str, str]]:
    """
    Вердикт по апсайду Base-сценария: (подпись, ключ цвета).
    None — если апсайд неизвестен (DCF неприменим / справедливая ≤ 0).
    """
    if upside is None:
        return None
    if upside >= VERDICT_BAND:
        return "НЕДООЦЕНЕНА", "pos"
    if upside <= -VERDICT_BAND:
        return "ПЕРЕОЦЕНЕНА", "neg"
    return "СПРАВЕДЛИВО", "text_dim"


def c(key: str) -> str:
    """Короткий доступ к цвету по токену (для f-строк в разметке)."""
    return COLORS[key]


_CSS = f"""
<style>
    /* ── Базовые поверхности ─────────────────────────────────────────── */
    .stApp {{ background:{COLORS['bg']}; }}

    .metric-card {{
        background:{COLORS['surface']}; border:1px solid {COLORS['border']};
        border-radius:14px; padding:14px 16px; margin:4px 0;
    }}
    .metric-label {{
        color:{COLORS['text_muted']}; font-size:10px; text-transform:uppercase;
        letter-spacing:0.06em; font-weight:600;
    }}
    .metric-value {{
        color:{COLORS['text']}; font-size:22px; font-weight:700;
        margin-top:3px; overflow-wrap:anywhere; letter-spacing:-0.01em;
    }}
    .metric-sub {{ color:{COLORS['text_dim']}; font-size:11.5px; margin-top:3px; line-height:1.55; }}

    .section-header {{
        color:{COLORS['text']}; font-size:16px; font-weight:600;
        margin:22px 0 10px 0; letter-spacing:-0.01em;
    }}

    /* ── st.metric в тон карточкам ───────────────────────────────────── */
    div[data-testid="stMetric"] {{
        background:{COLORS['surface']}; border:1px solid {COLORS['border']};
        border-radius:14px; padding:12px 14px;
    }}
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
        color:{COLORS['text']}; font-size:1.4rem; line-height:1.2;
        overflow-wrap:anywhere; white-space:normal;
    }}
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] {{ color:{COLORS['text_dim']}; }}
    div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {{ font-size:0.78rem; }}

    /* ── Сравнение: подсветка лучшего/худшего ────────────────────────── */
    .cmp-best  {{ color:{COLORS['pos']}; font-weight:700; }}
    .cmp-worst {{ color:{COLORS['neg']}; font-weight:600; }}

    /* ── Мелочи ──────────────────────────────────────────────────────── */
    .upside-pos {{ color:{COLORS['pos']}; font-weight:700; }}
    .upside-neg {{ color:{COLORS['neg']}; font-weight:700; }}
    hr {{ border-color:{COLORS['border']}; }}
</style>
"""


def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `python3 -m pytest tests/test_theme.py -q`
Expected: PASS (6 passed)

- [ ] **Step 5: Обновить `.streamlit/config.toml` в тон**

```toml
# Тёмная тема «финтех» — цвета совпадают с токенами в ui/theme.py.
[theme]
base = "dark"
primaryColor = "#6366f1"
backgroundColor = "#0f1116"
secondaryBackgroundColor = "#16181f"
textColor = "#f4f4f5"
font = "sans serif"
```

- [ ] **Step 6: Полная сюита + commit**

Run: `python3 -m pytest -q`
Expected: `91 passed` (85 существующих + 6 новых)

```bash
git add ui/theme.py tests/test_theme.py .streamlit/config.toml
git commit -m "feat(ui): palette tokens in theme.py + verdict_for helper"
```

---

## Task 2: `ui/components.py` — цвета из токенов + новые компоненты

**Files:**
- Modify: `ui/components.py`

- [ ] **Step 1: Заменить блок констант в начале файла**

Найти и заменить:

```python
from core.data import fmt_large

_PLOT_BG = "#181825"
_GRID = "#313244"
_AXIS = "#6c7086"

_SCENARIO_META = {
    "bear": ("🐻 Bear", "scenario-bear", "#f38ba8"),
    "base": ("📊 Base", "scenario-base", "#89b4fa"),
    "bull": ("🐂 Bull", "scenario-bull", "#a6e3a1"),
}
```

на:

```python
from core.data import fmt_large
from ui.theme import COLORS, SCENARIO_META, verdict_for

_PLOT_BG = COLORS["surface"]
_GRID = COLORS["border"]
_AXIS = COLORS["text_muted"]

# подпись + цвет сценария берём из общих токенов
_SCENARIO_EMOJI = {"bear": "🐻", "base": "📊", "bull": "🐂"}


def _scenario(name):
    """(подпись с эмодзи, цвет) для сценария bear/base/bull."""
    label, color_key = SCENARIO_META[name]
    return f"{_SCENARIO_EMOJI[name]} {label}", COLORS[color_key]
```

- [ ] **Step 2: Починить использования старого `_SCENARIO_META`**

В `scenario_card` заменить строку:
```python
    label, css_class, _ = _SCENARIO_META[name]
```
на:
```python
    label, accent = _scenario(name)
```
и в разметке карточки заменить `class="metric-card {css_class}"` на
`class="metric-card" style="border-left:3px solid {accent}"`.

В `dcf_fair_value` заменить строки:
```python
    labels = [_SCENARIO_META[n][0] for n in order]
    intrinsics = [dcf_results[n].intrinsic for n in order]
    colors = [_SCENARIO_META[n][2] for n in order]
```
на:
```python
    labels = [_scenario(n)[0] for n in order]
    intrinsics = [dcf_results[n].intrinsic for n in order]
    colors = [_scenario(n)[1] for n in order]
```

В `dcf_waterfall` заменить `marker_color=["#89b4fa"] * years + ["#cba6f7"]` на
`marker_color=[COLORS["accent"]] * years + [COLORS["accent2"]]`, а
`textfont=dict(color="#cdd6f4", size=10)` на `textfont=dict(color=COLORS["text"], size=10)`.

В `price_chart` заменить `line=dict(color="#89b4fa", width=2)` на
`line=dict(color=COLORS["accent"], width=2)` и
`fillcolor="rgba(137,180,250,0.08)"` на `fillcolor="rgba(99,102,241,0.10)"`.

В `financials_history` заменить `marker_color="#89b4fa"` на `marker_color=COLORS["accent"]`,
`line=dict(color="#a6e3a1", width=3)` на `line=dict(color=COLORS["pos"], width=3)`,
`color="#89b4fa"` в `yaxis` на `color=COLORS["accent"]`,
`yaxis2=dict(color="#a6e3a1"...` на `yaxis2=dict(color=COLORS["pos"]...`,
`legend=dict(bgcolor="#1e1e2e", bordercolor=_GRID)` на
`legend=dict(bgcolor=COLORS["surface"], bordercolor=_GRID)`.

В `reverse_dcf_cards` заменить `class="metric-card scenario-base"` (оба места) на
`class="metric-card" style="border-left:3px solid {COLORS['accent']}"` и
`<b style='color:#a6e3a1'>` на `<b style='color:{COLORS["pos"]}'>`.

В `sensitivity_table` заменить `color:#6c7086` на `color:{COLORS['text_muted']}`,
`border:2px solid #f9e2af` на `border:2px solid {COLORS['warn']}`,
`background:#1e1e2e` на `background:{COLORS['surface']}`,
`border:1px solid #45475a` на `border:1px solid {COLORS['border']}`,
`color:#a6adc8` на `color:{COLORS['text_dim']}`.

- [ ] **Step 3: Дописать новые компоненты в конец `ui/components.py`**

```python
def ticker_header(td) -> None:
    """Хедер тикера: аватар-градиент, название, сектор, цена и дневное изменение."""
    chg = td.day_change_pct
    chg_color = COLORS["pos"] if chg >= 0 else COLORS["neg"]
    sign = "+" if chg >= 0 else ""
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:13px;margin-bottom:16px">
      <div style="width:44px;height:44px;border-radius:13px;flex:none;
      background:linear-gradient(135deg,{COLORS['accent']},{COLORS['accent2']});
      display:flex;align-items:center;justify-content:center;
      color:#fff;font-weight:700;font-size:18px">{td.symbol[:1]}</div>
      <div style="flex:1;min-width:0">
        <div style="color:{COLORS['text']};font-size:19px;font-weight:600;
        letter-spacing:-0.01em;overflow:hidden;text-overflow:ellipsis;
        white-space:nowrap">{td.name}</div>
        <div style="color:{COLORS['text_muted']};font-size:12px">{td.symbol} · {td.sector}</div>
      </div>
      <div style="text-align:right;flex:none">
        <div style="color:{COLORS['text']};font-size:22px;font-weight:700">${td.price:.2f}</div>
        <div style="color:{chg_color};font-size:12.5px;font-weight:600">{sign}{chg:.2f}%</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def scenario_scale(bear: float, base: float, bull: float, price: float) -> str:
    """
    HTML-шкала bear/base/bull относительно рыночной цены.
    Возвращает разметку (вставляется внутрь карточки-вердикта).
    """
    hi = max(bull, price) * 1.05
    pct = lambda v: max(0.0, min(100.0, v / hi * 100)) if hi > 0 else 0.0
    return f"""
    <div style="position:relative;height:6px;background:{COLORS['elevated']};
    border-radius:3px;margin:12px 0 6px">
      <div style="position:absolute;left:0;width:{pct(base):.1f}%;height:100%;
      background:linear-gradient(90deg,{COLORS['neg']},{COLORS['warn']});border-radius:3px"></div>
      <div style="position:absolute;left:{pct(bull):.1f}%;width:2px;height:12px;top:-3px;
      background:{COLORS['pos']};border-radius:1px"></div>
      <div style="position:absolute;left:{pct(price):.1f}%;width:2px;height:12px;top:-3px;
      background:{COLORS['text']};border-radius:1px"></div>
    </div>
    <div style="display:flex;justify-content:space-between;color:{COLORS['text_muted']};font-size:10px">
      <span>bear ${bear:.0f}</span>
      <span style="color:{COLORS['text_dim']}">base ${base:.0f}</span>
      <span style="color:{COLORS['pos']}">bull ${bull:.0f}</span>
      <span style="color:{COLORS['text']};font-weight:600">рынок ${price:.0f}</span>
    </div>
    """


def verdict_card(dcf_results, price: float, wacc: float) -> None:
    """
    Карточка-вердикт: НЕДООЦЕНЕНА / СПРАВЕДЛИВО / ПЕРЕОЦЕНЕНА, справедливая цена,
    апсайд и шкала сценариев. Главный блок страницы «Анализ».
    """
    base_iv = dcf_results["base"].intrinsic
    upside = ((base_iv - price) / price * 100) if (price and base_iv > 0) else None
    v = verdict_for(upside)

    if v is None:
        st.markdown(f"""
        <div style="background:{COLORS['surface']};border:1px solid {COLORS['border']};
        border-radius:16px;padding:18px;margin-bottom:12px">
          <div style="color:{COLORS['text_dim']};font-size:13px">
            Справедливая цена не определяется: расчётная стоимость собственного
            капитала ≤ 0 (долг и SBC съедают денежный поток).
          </div>
        </div>
        """, unsafe_allow_html=True)
        return

    label, ckey = v
    tint = COLORS[ckey]
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{tint}22,{tint}08);
    border:1px solid {tint}44;border-radius:16px;padding:18px;margin-bottom:12px">
      <div style="display:flex;align-items:center;gap:9px;margin-bottom:10px">
        <span style="background:{tint}33;color:{tint};font-size:10px;font-weight:700;
        padding:4px 11px;border-radius:99px;letter-spacing:0.04em">{label}</span>
        <span style="color:{COLORS['text_muted']};font-size:11px">
        DCF · Base · WACC {wacc*100:.1f}%</span>
      </div>
      <div style="display:flex;align-items:flex-end;gap:14px">
        <div>
          <div style="color:{COLORS['text_dim']};font-size:11px;margin-bottom:2px">Справедливая цена</div>
          <div style="color:{COLORS['text']};font-size:32px;font-weight:700;
          letter-spacing:-0.02em">${base_iv:.2f}</div>
        </div>
        <div style="padding-bottom:6px">
          <div style="color:{tint};font-size:18px;font-weight:700">{upside:+.1f}%</div>
        </div>
      </div>
      {scenario_scale(dcf_results['bear'].intrinsic, base_iv,
                      dcf_results['bull'].intrinsic, price)}
    </div>
    """, unsafe_allow_html=True)


def metric_rows(pairs) -> None:
    """Компактные строки «подпись — значение» вместо стены одинаковых плиток.
    pairs: список кортежей (подпись, значение-строка)."""
    rows = "".join(
        f"""<div style="display:flex;justify-content:space-between;padding:9px 14px;
        border-bottom:1px solid {COLORS['elevated']}">
          <span style="color:{COLORS['text_dim']};font-size:12.5px">{k}</span>
          <span style="color:{COLORS['text']};font-size:12.5px;font-weight:600">{v}</span>
        </div>""" for k, v in pairs)
    st.markdown(f"""
    <div style="background:{COLORS['surface']};border:1px solid {COLORS['border']};
    border-radius:14px;overflow:hidden">{rows}</div>
    """, unsafe_allow_html=True)
```

- [ ] **Step 4: Обновить сигнатуру `reverse_dcf_cards` под живую ставку**

Страница будет передавать живую доходность 10-леток, поэтому меняем сигнатуру
здесь же (до того, как страница начнёт её так вызывать). Заменить строку:

```python
def reverse_dcf_cards(implied_growth_value, implied_return_value,
                      terminal_growth: float, revenue_growth) -> None:
```
на:
```python
def reverse_dcf_cards(implied_growth_value, implied_return_value,
                      terminal_growth: float, revenue_growth, risk_free=None) -> None:
```

И внутри, в ветке где `implied_return_value is not None`, заменить строку:
```python
            sub = ("годовых при росте Base-сценария<br>"
                   "Ориентир: гособлигации США 10 лет ≈ 4%")
```
на:
```python
            ref = (f"{risk_free*100:.1f}%" if risk_free else "4%")
            sub = ("годовых при росте Base-сценария<br>"
                   f"Ориентир: гособлигации 10 лет ≈ {ref}")
```

- [ ] **Step 5: Проверить импорт и сюиту**

Run: `python3 -c "import ui.components; print('ok')" 2>&1 | grep -v Warning && python3 -m pytest -q 2>&1 | tail -1`
Expected: `ok`, `91 passed`

- [ ] **Step 6: Commit**

```bash
git add ui/components.py
git commit -m "feat(ui): components use palette tokens; add verdict card, scale, metric rows, header"
```

---

## Task 3: `pages/1_📊_Анализ.py` — пересборка порядка

**Files:**
- Modify: `pages/1_📊_Анализ.py`

READ THE FILE FIRST. Логику расчётов НЕ трогаем — меняется только порядок и подача.

- [ ] **Step 1: Заменить хедер и блок быстрых метрик**

Найти блок от `# ─── Хедер + кнопка в избранное ───` до строки `C.price_chart(td.history)` включительно и заменить на:

```python
# ─── Хедер + кнопка в избранное ─────────────────────────────────────────────
head, fav = st.columns([6, 1])
with head:
    C.ticker_header(td)
with fav:
    if st.button("⭐ В избранное", use_container_width=True):
        add_favorite(td.symbol)
        st.toast(f"{td.symbol} добавлен в избранное")
```

(график цены переедет ниже — он появится после вердикта)

- [ ] **Step 2: Вердикт сразу после хедера**

Сразу после блока из Step 1 (до `C.section_header("📊 Мультипликаторы")`) вставить —
это использует уже существующие ниже переменные, поэтому **блок расчёта DCF надо
поднять сюда**. Найти существующий блок:

```python
# ─── DCF ────────────────────────────────────────────────────────────────────
C.section_header("🔮 DCF — три сценария")
# База FCF: с поправкой на SBC (если галочка и данные есть) или без неё
use_sbc = params.subtract_sbc and td.fcf_normalized_ex_sbc is not None
fcf_base = td.fcf_normalized_ex_sbc if use_sbc else td.fcf_normalized

# ─── Действующий WACC: CAPM по бете (auto) или ползунок ─────────────────────
rf, rf_live = load_risk_free()
wacc_est = estimate_wacc_for(td, rf) if params.wacc_auto else None
eff_wacc = wacc_est.wacc if wacc_est is not None else params.wacc
```

Вырезать его целиком и вставить сразу после хедера, убрав строку
`C.section_header("🔮 DCF — три сценария")`. Затем сразу за ним — рендер вердикта:

```python
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
    )
    C.verdict_card(dcf, td.price, eff_wacc)

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
    st.caption((f"{base_note}{wacc_note} · горизонт {params.years} лет · "
                f"терм. рост {params.terminal_growth*100:.1f}%").replace("$", "\\$"))
```

- [ ] **Step 3: График цены + ключевые метрики строками**

Сразу после блока из Step 2 вставить:

```python
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
```

- [ ] **Step 4: Остальное — в сворачиваемые блоки**

Заменить существующие блоки «Мультипликаторы», «Финансовые показатели (TTM)» и
«О компании» на свёрнутые expander'ы:

```python
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
```

- [ ] **Step 5: Детали DCF — в сворачиваемый блок**

Заменить оставшиеся блоки (карточки сценариев, предупреждение о TV, waterfall,
график справедливой цены, сетка чувствительности) на один expander:

```python
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

        st.markdown("##### Чувствительность (WACC × терминальный рост)")
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
            st.caption("Жёлтой рамкой отмечены текущие настройки. «—» — терминальный "
                       "рост ≥ WACC, модель Гордона неприменима.")

with st.expander("📅 История финансов"):
    C.financials_history(td.financials)
```

- [ ] **Step 6: Проверка — компиляция, сюита, AppTest на трёх тикерах**

Run: `python3 -m py_compile "pages/1_📊_Анализ.py" ui/components.py && echo ok && python3 -m pytest -q 2>&1 | tail -1`
Expected: `ok`, `91 passed`

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -c "
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
for sym in ['AAPL','INTC','AMZN']:
    at = AppTest.from_file('pages/1_📊_Анализ.py', default_timeout=90)
    at.run(); at.text_input[0].set_value(sym).run()
    print(f'{sym}: exception={bool(at.exception)}')
    if at.exception: print('  ', at.exception)
" 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn|No runtime|ScriptRunContext"
```
Expected: у всех трёх `exception=False` (AAPL — вердикт ПЕРЕОЦЕНЕНА, INTC — сообщение о неприменимости, AMZN — либо вердикт, либо нейтральная карточка). PASTE OUTPUT.

- [ ] **Step 7: Commit**

```bash
git add "pages/1_📊_Анализ.py" ui/components.py
git commit -m "feat(ui): verdict-first Analysis layout, collapsible detail sections"
```

---

## Task 4: Перекраска остальных страниц

**Files:**
- Modify: `pages/2_⚖️_Сравнение.py`, `pages/3_⭐_Избранное.py`, `pages/4_💎_Идеи.py`

READ EACH FILE FIRST.

- [ ] **Step 1: `pages/2_⚖️_Сравнение.py`**

Добавить импорт `from ui.theme import COLORS` и в HTML-таблице заменить:
`background:#1e1e2e` → `background:{COLORS['surface']}`,
`border:1px solid #313244` → `border:1px solid {COLORS['border']}`,
`color:#a6adc8` → `color:{COLORS['text_dim']}`.

- [ ] **Step 2: `pages/3_⭐_Избранное.py`**

Изменений цветов не требуется (страница использует только `st.metric` и
`st.markdown` без захардкоженных цветов) — проверить это командой:

Run: `grep -n "#[0-9a-fA-F]\{6\}" "pages/3_⭐_Избранное.py" || echo "захардкоженных цветов нет"`
Expected: `захардкоженных цветов нет`. Если цвета найдутся — заменить на токены `COLORS`.

- [ ] **Step 3: `pages/4_💎_Идеи.py`**

Добавить импорт `from ui.theme import COLORS` и заменить захардкоженные цвета
в блоке карточек:
`border = "#3a2a45" if risk else "#313244"` → `border = COLORS["warn"] + "55" if risk else COLORS["border"]`,
`bg = "#171320" if risk else "#1e1e2e"` → `bg = COLORS["warn"] + "0f" if risk else COLORS["surface"]`,
`up_col = "#a6e3a1" if (up or 0) >= 0 else "#f38ba8"` → `up_col = COLORS["pos"] if (up or 0) >= 0 else COLORS["neg"]`,
`color:#cdd6f4` → `color:{COLORS['text']}`,
`color:#6c7086` → `color:{COLORS['text_muted']}`,
`color:#a6adc8` → `color:{COLORS['text_dim']}`,
`color:#f5f5fa` → `color:{COLORS['text']}`,
`rgba(249,226,175,0.18);color:#f9e2af` → `{COLORS['warn']}33;color:{COLORS['warn']}`,
`<b style='color:#a6e3a1'>` → `<b style='color:{COLORS["pos"]}'>`.

- [ ] **Step 4: Проверка всех страниц**

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && python3 -m py_compile pages/*.py && echo "compile ok" && python3 -c "
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
for p in ['pages/1_📊_Анализ.py','pages/2_⚖️_Сравнение.py','pages/3_⭐_Избранное.py','pages/4_💎_Идеи.py']:
    at = AppTest.from_file(p, default_timeout=120); at.run()
    print(f\"  {p.split('/')[-1]:28} exception: {bool(at.exception)}\")
    if at.exception: print('   ', at.exception)
" 2>&1 | grep -viE "NotOpenSSL|urllib3|warnings.warn|No runtime|ScriptRunContext"
```
Expected: `compile ok`, у всех четырёх `exception: False`.

- [ ] **Step 5: Commit**

```bash
git add pages/
git commit -m "style(ui): repaint Compare/Favorites/Ideas with palette tokens"
```

---

## Task 5: Визуальная проверка и доки (выполняет контроллер)

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Запустить приложение и посмотреть глазами**

Run:
```bash
cd "/Users/vsevolodsamsonov/Claude/Projects/Stock Analysator" && pkill -f "streamlit run" 2>/dev/null; sleep 2 && (python3 -m streamlit run app.py --server.headless true --server.port 8501 > /tmp/st_redesign.log 2>&1 &) && sleep 9 && curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8501/
```
Expected: `HTTP 200`

Проверить в браузере на `http://localhost:8501`:
- **Анализ (AAPL)**: аватар, вердикт «ПЕРЕОЦЕНЕНА» с красным градиентом, шкала
  bear/base/bull с маркером рынка, две карточки реверс-DCF, график, ключевые
  метрики строками, ниже свёрнутые блоки.
- **Анализ (INTC)**: вместо вердикта — сообщение о неприменимости DCF, страница
  не падает.
- **Идеи / Сравнение / Избранное**: цвета в тон, ничего не «светит» старой
  палитрой.

- [ ] **Step 2: Обновить `CLAUDE.md`**

В раздел «## Стек и запуск» после строки про `ui/` добавить:

```markdown
- Дизайн: тёмная «финтех»-палитра. **Все цвета — токены `COLORS` в `ui/theme.py`**,
  дублировать хардкодом в компонентах/страницах нельзя. На «Анализе» главный блок —
  карточка-вердикт (НЕДООЦЕНЕНА/СПРАВЕДЛИВО/ПЕРЕОЦЕНЕНА, порог ±15%), детали
  спрятаны в сворачиваемые блоки.
```

- [ ] **Step 3: Финальная проверка и commit**

Run: `python3 -m pytest -q 2>&1 | tail -1`
Expected: `91 passed`

```bash
git add CLAUDE.md
git commit -m "docs: document dark-fintech design system"
```

- [ ] **Step 4: НЕ пушить без разрешения владельца**

**СТОП:** `git push` = автодеплой публичного приложения. Только с явного «пуш».

---

## Задел на будущее (НЕ сейчас — YAGNI)

- Светлая тема с переключателем (владелец выбрал только тёмную).
- Анимации переходов между вкладками.
- Адаптив под мобилку (Streamlit частично делает сам).
