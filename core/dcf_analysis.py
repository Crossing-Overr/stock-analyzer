from dataclasses import dataclass
from typing import Optional

from core.dcf import run_dcf, dcf_upside_base
from core.wacc import effective_wacc_for

# Диапазоны поиска для обратных задач
GROWTH_LO = -0.50
GROWTH_HI = 1.00
RETURN_HI = 0.50

# Сетка чувствительности WACC x терминальный рост
WACC_STEP = 0.01     # 1 п.п.
TG_STEP = 0.005      # 0.5 п.п.
MULT_STEP = 2.0      # шаг оси мультипликатора в сетке чувствительности
GRID_RADIUS = 2      # ±2 шага → сетка 5×5


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
                   terminal_multiple=None,
                   lo: float = GROWTH_LO, hi: float = GROWTH_HI) -> Optional[float]:
    """
    Стартовый рост FCF, при котором справедливая цена = рыночной,
    т.е. «какой рост уже заложен в текущую цену».

    None, если FCF ≤ 0 / нет акций / нет цены, либо решения нет в [lo, hi].
    """
    if not _inputs_valid(price, fcf_base, shares):
        return None

    def f(g):
        return _intrinsic(fcf_base, g, wacc, terminal_growth, years, shares, net_debt,
                          terminal_multiple) - price

    return _bisect(f, lo, hi)


def implied_return(price, fcf_base, shares, net_debt, growth_start, terminal_growth, years,
                   terminal_multiple=None, hi: float = RETURN_HI) -> Optional[float]:
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
        return _intrinsic(fcf_base, growth_start, r, terminal_growth, years, shares,
                          net_debt, terminal_multiple) - price

    return _bisect(f, lo, hi)


@dataclass
class SensitivityCell:
    wacc: float
    terminal_growth: Optional[float]   # None в режиме мультипликатора
    multiple: Optional[float]          # None в режиме Гордона
    intrinsic: Optional[float]         # None, если терм. рост >= WACC (Гордон неприменим)
    upside: Optional[float]            # % к текущей цене
    is_current: bool                   # ячейка текущих настроек ползунков


@dataclass
class SensitivityGrid:
    waccs: list                          # значения по столбцам
    terminal_growths: Optional[list]     # ось строк в режиме Гордона (иначе None)
    multiples: Optional[list]            # ось строк в режиме мультипликатора (иначе None)
    cells: list                          # list[list[SensitivityCell]]


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

    centre_val = terminal_multiple if use_mult else terminal_growth
    rows = []
    for rv in row_vals:
        row = []
        for w in waccs:
            is_current = (abs(w - wacc) < 1e-9) and (abs(rv - centre_val) < 1e-9)
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


def ticker_base_upside(td, params, risk_free) -> Optional[float]:
    """
    Апсайд Base-сценария по тикеру — одной строкой вместо трёх шагов
    (действующий WACC → база FCF с учётом SBC → апсайд), которые раньше
    дословно повторялись на страницах Сравнения и Избранного.

    `params` — объект с полями DcfParams (wacc_auto, wacc, growth_rates,
    terminal_growth, years, subtract_sbc); core не импортирует ui, поля читаются
    по «утиной типизации». None, если DCF к тикеру неприменим.
    """
    wacc = effective_wacc_for(td, risk_free, auto=params.wacc_auto, manual=params.wacc)
    return dcf_upside_base(
        td.dcf_fcf_base(params.subtract_sbc), td.price, td.shares_outstanding,
        td.net_debt, params.growth_rates, wacc, params.terminal_growth, params.years,
        terminal_multiple=getattr(params, "terminal_multiple", None),
    )
