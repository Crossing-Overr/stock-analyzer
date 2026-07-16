from dataclasses import dataclass
from typing import Optional

from core.dcf import run_dcf

# Диапазоны поиска для обратных задач
GROWTH_LO = -0.50
GROWTH_HI = 1.00
RETURN_HI = 0.50

# Сетка чувствительности WACC x терминальный рост
WACC_STEP = 0.01     # 1 п.п.
TG_STEP = 0.005      # 0.5 п.п.
GRID_RADIUS = 2      # ±2 шага → сетка 5×5


def _intrinsic(fcf_base, growth_start, wacc, terminal_growth, years, shares, net_debt) -> float:
    """Справедливая цена одного сценария. Тонкая обёртка над моделью."""
    res = run_dcf(
        fcf_base=fcf_base,
        growth_rates={"base": growth_start},
        wacc=wacc,
        terminal_growth=terminal_growth,
        years=years,
        shares=shares,
        net_debt=net_debt,
    )
    return res["base"].intrinsic


def _bisect(f, lo: float, hi: float, tol: float = 1e-7, max_iter: int = 200) -> Optional[float]:
    """
    Корень f(x)=0 на [lo, hi] делением отрезка пополам.

    Работает, потому что справедливая цена монотонна по обоим искомым
    параметрам (растёт с ростом FCF, падает с ростом ставки). Если на концах
    отрезка знак не меняется — решения в диапазоне нет, возвращаем None
    (лучше честный None, чем выдуманное число на границе).
    """
    f_lo = f(lo)
    f_hi = f(hi)
    if f_lo == 0:
        return lo
    if f_hi == 0:
        return hi
    if (f_lo > 0) == (f_hi > 0):
        return None
    for _ in range(max_iter):
        if (hi - lo) < tol:
            break
        mid = (lo + hi) / 2
        f_mid = f(mid)
        if f_mid == 0:
            return mid
        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi, f_hi = mid, f_mid
    return (lo + hi) / 2


def _inputs_valid(price, fcf_base, shares) -> bool:
    return bool(fcf_base and fcf_base > 0 and shares and shares > 0 and price and price > 0)


def implied_growth(price, fcf_base, shares, net_debt, wacc, terminal_growth, years,
                   lo: float = GROWTH_LO, hi: float = GROWTH_HI) -> Optional[float]:
    """
    Стартовый рост FCF, при котором справедливая цена = рыночной,
    т.е. «какой рост уже заложен в текущую цену».

    None, если FCF ≤ 0 / нет акций / нет цены, либо решения нет в [lo, hi].
    """
    if not _inputs_valid(price, fcf_base, shares):
        return None

    def f(g):
        return _intrinsic(fcf_base, g, wacc, terminal_growth, years, shares, net_debt) - price

    return _bisect(f, lo, hi)


def implied_return(price, fcf_base, shares, net_debt, growth_start, terminal_growth, years,
                   hi: float = RETURN_HI) -> Optional[float]:
    """
    Ставка дисконтирования, при которой справедливая цена = рыночной, т.е.
    «сколько годовых даст покупка по текущей цене при заданном росте».

    Нижняя граница поиска — чуть выше терминального роста: ниже него модель
    Гордона ломается (знаменатель wacc - g становится ≤ 0).
    """
    if not _inputs_valid(price, fcf_base, shares):
        return None

    lo = terminal_growth + 0.001
    if lo >= hi:
        return None

    def f(r):
        return _intrinsic(fcf_base, growth_start, r, terminal_growth, years, shares, net_debt) - price

    return _bisect(f, lo, hi)


@dataclass
class SensitivityCell:
    wacc: float
    terminal_growth: float
    intrinsic: Optional[float]   # None, если терм. рост >= WACC (модель Гордона неприменима)
    upside: Optional[float]      # % к текущей цене
    is_current: bool             # ячейка текущих настроек ползунков


@dataclass
class SensitivityGrid:
    waccs: list              # значения по столбцам
    terminal_growths: list   # значения по строкам
    cells: list              # list[list[SensitivityCell]], строки — по terminal_growths


def sensitivity_grid(fcf_base, price, shares, net_debt, growth_start,
                     wacc, terminal_growth, years,
                     wacc_step: float = WACC_STEP, tg_step: float = TG_STEP,
                     radius: int = GRID_RADIUS) -> Optional[SensitivityGrid]:
    """
    Сетка «WACC × терминальный рост» вокруг текущих настроек. Рост FCF берётся
    базовый (Base-сценарий) и не варьируется — меняются только ставки.
    None, если DCF в принципе неприменим (FCF ≤ 0 и т.п.).
    """
    if not _inputs_valid(price, fcf_base, shares):
        return None

    waccs = [wacc + i * wacc_step for i in range(-radius, radius + 1)]
    tgs = [terminal_growth + i * tg_step for i in range(-radius, radius + 1)]

    rows = []
    for tg in tgs:
        row = []
        for w in waccs:
            is_current = (abs(w - wacc) < 1e-9) and (abs(tg - terminal_growth) < 1e-9)
            if tg >= w:
                row.append(SensitivityCell(w, tg, None, None, is_current))
                continue
            iv = _intrinsic(fcf_base, growth_start, w, tg, years, shares, net_debt)
            upside = (iv - price) / price * 100 if iv > 0 else None
            row.append(SensitivityCell(w, tg, iv, upside, is_current))
        rows.append(row)

    return SensitivityGrid(waccs=waccs, terminal_growths=tgs, cells=rows)
