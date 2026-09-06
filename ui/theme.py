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
