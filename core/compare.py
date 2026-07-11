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
