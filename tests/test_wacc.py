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
