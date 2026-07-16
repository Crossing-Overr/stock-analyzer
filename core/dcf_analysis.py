from typing import Optional

from core.dcf import run_dcf

# Диапазоны поиска для обратных задач
GROWTH_LO = -0.50
GROWTH_HI = 1.00
RETURN_HI = 0.50


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
