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


def estimate_wacc_for(td, risk_free) -> Optional[WaccEstimate]:
    """Как estimate_wacc, но берёт бету/кап-ю/долг из TickerData — без повторения
    `td.beta, rf, td.market_cap, td.total_debt` на каждой странице."""
    return estimate_wacc(td.beta, risk_free, td.market_cap, td.total_debt)


def effective_wacc_for(td, risk_free, auto: bool, manual: float) -> float:
    """Действующий WACC по TickerData (CAPM в авто-режиме или ползунок)."""
    return effective_wacc(td.beta, risk_free, td.market_cap, td.total_debt,
                          auto=auto, manual=manual)
