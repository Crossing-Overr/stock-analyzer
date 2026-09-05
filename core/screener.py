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
